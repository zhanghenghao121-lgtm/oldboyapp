from unittest.mock import patch
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image

from apps.ai_customer.llm_clients import LLMClientError, chat_completion
from apps.ai_customer.ai_image_services import _task_result_images
from apps.ai_customer.models import (
    SceneInferenceJob,
    SceneInferenceProject,
    StoryboardAsset,
    StoryboardPanel,
    StoryboardProject,
    StorySegment,
)
from apps.ai_customer.scene_inference_services import (
    create_scene_inference_project,
    enhance_scene_screenshot,
    generate_scene_inference_views,
    generate_scene_panorama,
    refresh_scene_inference_project,
)
from apps.ai_customer.storyboard_services import (
    analyze_project,
    compose_grid,
    delete_asset,
    generate_panels,
    generate_video_prompts,
    refresh_panel_images,
    regenerate_panel,
    save_asset,
)
from apps.storage.models import UploadedFileRecord


class StoryboardServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="director", password="pass1234")
        self.project = StoryboardProject.objects.create(
            user=self.user,
            title="未命名故事板",
            original_story="雨夜的站台上，林初拿着旧车票等待。列车驶入后，她看见车窗内久别的父亲，缓慢向前一步。",
            analysis_model="deepseek-v4-pro",
        )

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_analyze_project_creates_leaf_segment_and_required_assets(self, call_model):
        call_model.side_effect = [
            {
                "project_title": "雨夜重逢",
                "scene_blocks": [
                    {
                        "order": 1,
                        "scene_number": "S01",
                        "title": "站台等待",
                        "location": "火车站台",
                        "time_of_day": "雨夜",
                        "characters": ["林初", "父亲"],
                        "mood": "克制",
                        "summary": "女主在列车到站时看见父亲",
                        "original_text": self.project.original_story,
                        "split_reason": "单一站台场景",
                    }
                ],
            },
            {
                "can_be_9_grid": True,
                "score": 91,
                "panel_count": 6,
                "panel_count_reason": "单人等待和情绪变化较慢",
                "reason": "动作连续",
                "analysis": "一次重逢",
                "children": [],
            },
            {"characters": [{"name": "林初", "description": "女主"}], "scenes": [], "props": []},
        ]

        result = analyze_project(self.project)

        self.project.refresh_from_db()
        segment = StorySegment.objects.get(project=self.project)
        self.assertEqual(self.project.title, "雨夜重逢")
        self.assertEqual(segment.title, "S01 站台等待")
        self.assertEqual(segment.scene_name, "火车站台")
        self.assertEqual(segment.analysis_json["scene_context"]["characters"], ["林初", "父亲"])
        self.assertTrue(segment.is_leaf)
        self.assertEqual(segment.grid_feasibility_score, 91)
        self.assertEqual(segment.panel_count, 6)
        self.assertEqual(segment.required_assets_json["characters"][0]["name"], "林初")
        self.assertEqual(segment.assets.get().name, "林初")
        self.assertEqual(segment.assets.get().image_url, "")
        self.assertEqual(result["segments"][0]["scene_number"], "S01")
        self.assertEqual(result["segments"][0]["characters"], ["林初", "父亲"])
        self.assertEqual(len(result["segments"]), 1)

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_analyze_project_splits_scene_into_15s_children_with_panel_count(self, call_model):
        call_model.side_effect = [
            {
                "project_title": "雨夜重逢",
                "scene_blocks": [
                    {
                        "order": 1,
                        "scene_number": "S02",
                        "title": "车窗对望",
                        "location": "火车站台",
                        "time_of_day": "雨夜",
                        "characters": "林初、父亲",
                        "summary": "女主靠近车窗并与父亲对望",
                        "original_text": self.project.original_story,
                    }
                ],
            },
            {
                "can_be_9_grid": False,
                "score": 60,
                "reason": "包含等待和对望两个节奏",
                "analysis": "需要拆成两个 15 秒视频片段",
                "children": [
                    {
                        "order": 1,
                        "title": "等待列车",
                        "summary": "林初等待列车驶入",
                        "original_text": "林初拿着旧车票等待，列车驶入。",
                        "panel_count": 6,
                        "panel_count_reason": "单人情绪",
                    },
                    {
                        "order": 2,
                        "title": "车窗对望",
                        "summary": "林初看见父亲并向前一步",
                        "original_text": "她看见车窗内久别的父亲，缓慢向前一步。",
                        "panel_count": 9,
                        "panel_count_reason": "两人情绪递进",
                    },
                ],
            },
            {"can_be_9_grid": True, "score": 93, "panel_count": 6, "reason": "单人情绪", "analysis": "等待列车", "children": []},
            {"characters": [{"name": "林初", "description": "女主"}], "scenes": [{"name": "火车站台", "description": "雨夜"}], "props": []},
            {"can_be_9_grid": True, "score": 95, "panel_count": 9, "reason": "两人对望", "analysis": "重逢瞬间", "children": []},
            {"characters": [{"name": "林初", "description": "女主"}, {"name": "父亲", "description": "车窗内"}], "scenes": [], "props": []},
        ]

        analyze_project(self.project)

        root = StorySegment.objects.get(project=self.project, parent__isnull=True)
        children = list(root.children.order_by("order_index"))
        self.assertFalse(root.is_leaf)
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].panel_count, 6)
        self.assertEqual(children[1].panel_count, 9)
        self.assertEqual(children[1].analysis_json["scene_context"]["scene_number"], "S02")

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_long_scene_is_forced_to_split_even_when_model_marks_leaf(self, call_model):
        long_story = (
            "执事推开龙吟堂大门，众人从供桌旁退开。"
            "主角发现地上的灰烬呈现奇怪符号，低声询问来历。"
            "长老解释昨夜祭坛忽然熄灭，守夜弟子全部失踪。"
            "门外传来钟声，另一名弟子跌跌撞撞冲入堂内。"
            "他指认黑影从后山禁地逃走，众人情绪瞬间紧绷。"
            "主角决定带人追查，却被长老拦下要求先封锁山门。"
            "双方短暂争执后，供桌下突然滚出染血令牌。"
        )
        self.project.original_story = long_story
        self.project.save(update_fields=["original_story"])
        call_model.side_effect = [
            {
                "project_title": "龙吟堂",
                "scene_blocks": [
                    {
                        "order": 1,
                        "scene_number": "1-1",
                        "title": "龙吟堂覆灭余波",
                        "location": "龙吟堂",
                        "time_of_day": "日",
                        "characters": ["主角", "长老", "弟子"],
                        "summary": "龙吟堂内连续出现线索和冲突",
                        "original_text": long_story,
                    }
                ],
            },
            {
                "can_be_9_grid": True,
                "score": 95,
                "panel_count": 12,
                "reason": "模型误判为可直接表达",
                "analysis": "长场景",
                "children": [],
            },
            {
                "can_be_9_grid": False,
                "score": 72,
                "reason": "长场景需要拆成 15 秒小段",
                "analysis": "分为发现线索和突发指认",
                "children": [
                    {
                        "order": 1,
                        "title": "灰烬线索",
                        "summary": "主角发现灰烬符号并询问来历",
                        "original_text": "执事推开龙吟堂大门，众人从供桌旁退开。主角发现地上的灰烬呈现奇怪符号，低声询问来历。",
                        "panel_count": 9,
                    },
                    {
                        "order": 2,
                        "title": "弟子突入",
                        "summary": "弟子冲入并指认黑影，令牌制造新悬念",
                        "original_text": "门外传来钟声，另一名弟子跌跌撞撞冲入堂内。他指认黑影从后山禁地逃走，供桌下突然滚出染血令牌。",
                        "panel_count": 12,
                    },
                ],
            },
            {"can_be_9_grid": True, "score": 90, "panel_count": 9, "reason": "单个线索节奏", "analysis": "灰烬线索", "children": []},
            {"characters": [{"name": "主角", "description": "查案者"}], "scenes": [{"name": "龙吟堂", "description": "堂内"}], "props": []},
            {"can_be_9_grid": True, "score": 91, "panel_count": 12, "reason": "冲突和悬念", "analysis": "突发指认", "children": []},
            {"characters": [{"name": "弟子", "description": "报信者"}], "scenes": [], "props": [{"name": "染血令牌", "description": "关键线索"}]},
        ]

        analyze_project(self.project)

        root = StorySegment.objects.get(project=self.project, parent__isnull=True)
        children = list(root.children.order_by("order_index"))
        self.assertFalse(root.is_leaf)
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].title, "灰烬线索")
        self.assertEqual(children[1].panel_count, 12)

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_generate_panels_persists_exactly_nine_shots(self, call_model):
        segment = StorySegment.objects.create(
            project=self.project,
            level=1,
            title="站台重逢",
            original_text=self.project.original_story,
            is_leaf=True,
        )
        call_model.return_value = {
            "panels": [
                {"panel_no": number, "shot_type": "中景", "screen_description": f"画面 {number}", "image_prompt": f"提示词 {number}"}
                for number in range(1, 10)
            ]
        }

        result = generate_panels(segment)

        self.assertEqual(len(result), 9)
        self.assertEqual(segment.panels.count(), 9)
        self.assertEqual(segment.panels.get(panel_no=9).image_prompt, "提示词 9")

    def test_asset_can_be_created_without_image_then_deleted(self):
        segment = StorySegment.objects.create(project=self.project, title="站台", is_leaf=True)

        saved = save_asset(segment, {"asset_type": "scene", "name": "雨夜站台", "description": "潮湿地面"})

        self.assertEqual(saved["image_url"], "")
        delete_asset(segment, saved["id"])
        self.assertFalse(segment.assets.exists())

    def test_position_reference_asset_can_be_named_and_saved(self):
        segment = StorySegment.objects.create(project=self.project, title="站台", is_leaf=True)

        saved = save_asset(segment, {"asset_type": "position", "name": "父女对望站位", "image_url": "https://example.com/position.jpg"})

        self.assertEqual(saved["asset_type"], "position")
        self.assertEqual(segment.assets.get().name, "父女对望站位")

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_generate_panels_accepts_six_shots_and_supplementary_description(self, call_model):
        segment = StorySegment.objects.create(project=self.project, title="站台重逢", original_text=self.project.original_story, is_leaf=True)
        call_model.return_value = {
            "panels": [
                {"panel_no": number, "screen_description": f"画面 {number}", "image_prompt": f"提示词 {number}"}
                for number in range(1, 7)
            ]
        }

        result = generate_panels(segment, 6, "强调父女之间隔着列车窗")

        segment.refresh_from_db()
        self.assertEqual(len(result), 6)
        self.assertEqual(segment.panel_count, 6)
        self.assertEqual(segment.supplementary_description, "强调父女之间隔着列车窗")

    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_generate_video_prompts_updates_every_panel(self, call_model):
        segment = StorySegment.objects.create(project=self.project, title="站台重逢", is_leaf=True, panel_count=6)
        for number in range(1, 7):
            StoryboardPanel.objects.create(segment=segment, panel_no=number, screen_description=f"画面 {number}")
        call_model.return_value = {
            "panels": [
                {"panel_no": number, "video_prompt": f"【中景】【画面 {number}】（{5 if number == 6 else 2}秒）"}
                for number in range(1, 7)
            ]
        }

        result = generate_video_prompts(segment)

        self.assertEqual(len(result), 6)
        self.assertIn("【中景】", segment.panels.get(panel_no=1).video_prompt)

    @patch("apps.ai_customer.storyboard_services.requests.get")
    @patch("apps.ai_customer.storyboard_services.get_ai_image_task_result")
    def test_refresh_images_keeps_remote_url_when_transfer_download_fails(self, task_result, get):
        segment = StorySegment.objects.create(project=self.project, title="站台", is_leaf=True, panel_count=1)
        StoryboardPanel.objects.create(segment=segment, panel_no=1, generation_task_id="task-1")
        task_result.return_value = {"status": "succeeded", "images": ["https://cdn.example.com/panel.png"]}
        get.side_effect = Exception("temporary download blocked")

        result = refresh_panel_images(segment)

        self.assertEqual(result[0]["image_url"], "https://cdn.example.com/panel.png")
        self.assertEqual(segment.panels.get().image_url, "https://cdn.example.com/panel.png")

    @patch("apps.ai_customer.storyboard_services._upload_grid")
    @patch("apps.ai_customer.storyboard_services._download_image")
    def test_compose_grid_uses_portrait_tiles_without_cropping(self, download_image, upload_grid):
        self.project.aspect_ratio = "9:16"
        self.project.save(update_fields=["aspect_ratio"])
        segment = StorySegment.objects.create(project=self.project, title="竖屏分镜", is_leaf=True, panel_count=6)
        for number in range(1, 7):
            StoryboardPanel.objects.create(segment=segment, panel_no=number, image_url=f"https://example.com/{number}.png")
        download_image.return_value = Image.new("RGB", (360, 640), "#ffffff")

        def capture_grid(image_bytes, user):
            image = Image.open(io.BytesIO(image_bytes))
            self.assertEqual(image.size, (1080, 1280))
            return "https://assets.example.com/grid.png"

        upload_grid.side_effect = capture_grid

        url = compose_grid(segment, self.user)

        self.assertEqual(url, "https://assets.example.com/grid.png")
        self.assertEqual(download_image.call_count, 6)

    @patch("apps.ai_customer.storyboard_services._submit_panel_image")
    @patch("apps.ai_customer.storyboard_services._call_storyboard_json")
    def test_regenerate_one_panel_uses_selected_asset_and_updates_description(self, call_model, submit_image):
        segment = StorySegment.objects.create(project=self.project, title="站台", is_leaf=True)
        panel = StoryboardPanel.objects.create(segment=segment, panel_no=1, screen_description="旧画面", image_prompt="旧提示词")
        asset = StoryboardAsset.objects.create(project=self.project, segment=segment, asset_type="character", name="林初", image_url="https://example.com/lin.jpg")
        call_model.return_value = {"screen_description": "新画面", "image_prompt": "新提示词", "characters": ["林初"], "props": []}

        result = regenerate_panel(panel, {"asset_ids": [asset.id], "model": "gpt-image-2"})

        self.assertEqual(result["screen_description"], "新画面")
        self.assertEqual(result["image_prompt"], "新提示词")
        references = submit_image.call_args.args[2]
        self.assertEqual(references[0]["name"], "林初")


class SceneInferenceServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="scene-director", password="pass1234")
        UploadedFileRecord.objects.create(
            user=self.user,
            key="scene/front.png",
            url="https://assets.example.com/front.png",
            content_type="image/png",
            size=128,
        )
        UploadedFileRecord.objects.create(
            user=self.user,
            key="scene/back.png",
            url="https://assets.example.com/back.png",
            content_type="image/png",
            size=128,
        )
        UploadedFileRecord.objects.create(
            user=self.user,
            key="scene/screenshot.png",
            url="https://assets.example.com/screenshot.png",
            content_type="image/png",
            size=128,
        )

    def test_create_scene_inference_project_requires_owned_uploads(self):
        project = create_scene_inference_project(
            self.user,
            {
                "title": "龙吟堂空间",
                "model_key": "gpt-image-2",
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )

        self.assertEqual(project.status, SceneInferenceProject.STATUS_DRAFT)
        self.assertEqual(project.title, "龙吟堂空间")

    @patch("apps.ai_customer.scene_inference_services._reference_image_data_url")
    @patch("apps.ai_customer.scene_inference_services._persist_storyboard_png")
    @patch("apps.ai_customer.scene_inference_services.submit_ai_image_generation")
    def test_generate_scene_inference_views_persists_three_views(self, submit_image, persist_png, reference_data_url):
        reference_data_url.side_effect = lambda url, user: f"data:{url}"
        submit_image.side_effect = [
            {"status": "completed", "images": ["left-ref"]},
            {"status": "completed", "images": ["right-ref"]},
            {"status": "completed", "images": ["top-ref"]},
        ]
        persist_png.side_effect = [
            "https://assets.example.com/left.png",
            "https://assets.example.com/right.png",
            "https://assets.example.com/top.png",
        ]
        project = create_scene_inference_project(
            self.user,
            {
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )

        result = generate_scene_inference_views(project, {"model_key": "gpt-image-2"})

        self.assertEqual(result["status"], SceneInferenceProject.STATUS_INFERENCE_DONE)
        self.assertEqual(result["left_image_url"], "https://assets.example.com/left.png")
        self.assertEqual(result["right_image_url"], "https://assets.example.com/right.png")
        self.assertEqual(result["top_image_url"], "https://assets.example.com/top.png")
        self.assertEqual(SceneInferenceJob.objects.filter(project=project, status=SceneInferenceJob.STATUS_SUCCESS).count(), 3)
        self.assertEqual(submit_image.call_args_list[0].kwargs["size"], "16:9")
        self.assertEqual(len(submit_image.call_args_list[0].kwargs["reference_images"]), 2)

    @patch("apps.ai_customer.scene_inference_services._reference_image_data_url")
    @patch("apps.ai_customer.scene_inference_services._persist_storyboard_png")
    @patch("apps.ai_customer.scene_inference_services.submit_ai_image_generation")
    def test_generate_scene_panorama_uses_five_references_and_2_to_1_size(self, submit_image, persist_png, reference_data_url):
        reference_data_url.side_effect = lambda url, user: f"data:{url}"
        submit_image.return_value = {"status": "completed", "images": ["panorama-ref"]}
        persist_png.return_value = "https://assets.example.com/panorama.png"
        project = create_scene_inference_project(
            self.user,
            {
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )
        project.left_image_url = "https://assets.example.com/left.png"
        project.right_image_url = "https://assets.example.com/right.png"
        project.top_image_url = "https://assets.example.com/top.png"
        project.status = SceneInferenceProject.STATUS_INFERENCE_DONE
        project.save(update_fields=["left_image_url", "right_image_url", "top_image_url", "status"])

        result = generate_scene_panorama(project, {"model_key": "gpt-image-2"})

        self.assertEqual(result["status"], SceneInferenceProject.STATUS_PANORAMA_DONE)
        self.assertEqual(result["panorama_image_url"], "https://assets.example.com/panorama.png")
        self.assertEqual(submit_image.call_args.kwargs["size"], "2:1")
        self.assertEqual(len(submit_image.call_args.kwargs["reference_images"]), 5)

    @patch("apps.ai_customer.scene_inference_services._reference_image_data_url")
    @patch("apps.ai_customer.scene_inference_services.submit_ai_image_generation")
    def test_enhance_scene_screenshot_creates_async_job(self, submit_image, reference_data_url):
        reference_data_url.return_value = "data:image/png;base64,abc"
        submit_image.return_value = {"status": "submitted", "task_id": "task-hd"}
        project = create_scene_inference_project(
            self.user,
            {
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )

        result = enhance_scene_screenshot(
            project,
            {"image_url": "https://assets.example.com/screenshot.png", "model_key": "gpt-image-2"},
        )

        self.assertEqual(result["job_type"], SceneInferenceJob.TYPE_SCREENSHOT_ENHANCE)
        self.assertEqual(result["status"], SceneInferenceJob.STATUS_RUNNING)
        self.assertEqual(result["task_id"], "task-hd")
        self.assertEqual(submit_image.call_args.kwargs["size"], "16:9")
        self.assertEqual(submit_image.call_args.kwargs["resolution"], "4k")
        self.assertIn("保持原图的场景构图", submit_image.call_args.kwargs["prompt"])
        self.assertEqual(len(submit_image.call_args.kwargs["reference_images"]), 1)

    @patch("apps.ai_customer.scene_inference_services._reference_image_data_url")
    @patch("apps.ai_customer.scene_inference_services._persist_storyboard_png")
    @patch("apps.ai_customer.scene_inference_services.get_ai_image_task_result")
    @patch("apps.ai_customer.scene_inference_services.submit_ai_image_generation")
    def test_refresh_scene_inference_project_finishes_screenshot_job(self, submit_image, task_result, persist_png, reference_data_url):
        reference_data_url.return_value = "data:image/png;base64,abc"
        submit_image.return_value = {"status": "submitted", "task_id": "task-hd"}
        task_result.return_value = {"status": "completed", "progress": 100, "images": ["hd-ref"]}
        persist_png.return_value = "https://assets.example.com/screenshot-hd.png"
        project = create_scene_inference_project(
            self.user,
            {
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )
        enhance_scene_screenshot(
            project,
            {"image_url": "https://assets.example.com/screenshot.png", "model_key": "gpt-image-2"},
        )

        refreshed = refresh_scene_inference_project(project)

        screenshot_job = next(job for job in refreshed["jobs"] if job["job_type"] == SceneInferenceJob.TYPE_SCREENSHOT_ENHANCE)
        self.assertEqual(screenshot_job["status"], SceneInferenceJob.STATUS_SUCCESS)
        self.assertEqual(screenshot_job["image_url"], "https://assets.example.com/screenshot-hd.png")


class LLMClientErrorTests(TestCase):
    @patch("apps.ai_customer.llm_clients.requests.post")
    def test_authentication_failure_returns_actionable_message(self, post):
        post.return_value.status_code = 401
        post.return_value.json.return_value = {"error": {"message": "Authentication Fails"}}

        with self.assertRaisesMessage(LLMClientError, "认证失败，请在后台“AI模型配置”检查该模型的 API 地址和 API Key"):
            chat_completion(
                {"base_url": "https://api.example.com/v1", "api_key": "invalid"},
                {"model": "deepseek-v4-pro", "messages": []},
                service_name="故事板场景拆解模型（DeepSeek V4 Pro / deepseek-v4-pro）",
            )


class AIImageResultParsingTests(TestCase):
    def test_task_result_images_extracts_url_from_stringified_list(self):
        result = _task_result_images(
            {
                "result": {
                    "images": "['https://upload.apimart.ai/f/image/example.png']",
                }
            }
        )

        self.assertEqual(result, ["https://upload.apimart.ai/f/image/example.png"])
