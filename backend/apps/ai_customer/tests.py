from unittest.mock import patch
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from requests import ConnectionError, Timeout
from rest_framework.test import APIClient

from apps.ai_customer.llm_clients import LLMClientError, chat_completion, image_generation
from apps.ai_customer.ai_image_services import _image_urls, _task_result_images
from apps.ai_customer.models import (
    OctopusNote,
    OctopusNoteFolder,
    OctopusPlanetPublish,
    OctopusPlanetTagStat,
    PositionStickerAsset,
    PositionStickerComposition,
    SceneInferenceJob,
    SceneInferenceProject,
    StoryboardAsset,
    StoryboardPanel,
    StoryboardProject,
    StorySegment,
)
from apps.ai_customer.cutout_services import (
    CutoutError,
    create_sticker_composition,
    cutout_character,
    enhance_sticker_composite,
    list_sticker_compositions,
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


def _image_upload(name: str, image: Image.Image, content_type: str = "image/png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class CutoutServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sticker-user", password="pass1234")

    @patch("apps.ai_customer.cutout_services._upload_transparent_png")
    def test_transparent_mode_uploads_png_without_cutout(self, upload_png):
        def fake_upload(png_bytes, user):
            record = UploadedFileRecord.objects.create(
                user=user,
                key="images/cutouts/test/direct.png",
                url="https://cdn.example.com/direct.png",
                content_type="image/png",
                size=len(png_bytes),
            )
            saved = Image.open(io.BytesIO(png_bytes))
            self.assertEqual(saved.mode, "RGBA")
            self.assertLess(saved.getpixel((0, 0))[3], 255)
            return {"url": record.url, "key": record.key, "content_type": record.content_type, "size": record.size}, record

        upload_png.side_effect = fake_upload
        image = Image.new("RGBA", (8, 6), (255, 0, 0, 0))
        image.putpixel((4, 3), (0, 128, 255, 255))

        result = cutout_character(
            _image_upload("already-transparent.png", image),
            "transparent",
            self.user,
            save_to_library=True,
        )

        self.assertEqual(result["mode"], "transparent")
        self.assertEqual(result["width"], 8)
        self.assertEqual(result["height"], 6)
        asset = PositionStickerAsset.objects.get(user=self.user)
        self.assertEqual(asset.cutout_mode, "transparent")
        self.assertEqual(result["library_asset"]["mode"], "transparent")

    def test_transparent_mode_rejects_opaque_images(self):
        image = Image.new("RGB", (8, 6), (255, 255, 255))

        with self.assertRaisesMessage(CutoutError, "请上传带透明通道"):
            cutout_character(_image_upload("opaque.png", image), "transparent", self.user)

    def test_sticker_composition_history_persists_editable_snapshot(self):
        scene = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/sticker-scenes/scene.png",
            url="https://cdn.example.com/scene.png",
            content_type="image/png",
            size=100,
        )
        result = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/composites/result.png",
            url="https://cdn.example.com/result.png",
            content_type="image/png",
            size=100,
        )
        layer = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/cutouts/layer.png",
            url="https://cdn.example.com/layer.png",
            content_type="image/png",
            size=100,
        )

        saved = create_sticker_composition(
            self.user,
            {
                "title": "站位贴图",
                "scene_name": "场景.png",
                "scene_key": scene.key,
                "result_key": result.key,
                "blend_mode": "natural",
                "canvas_width": 960,
                "canvas_height": 540,
                "layers": [{"id": "character-1", "name": "角色", "key": layer.key, "left": 12, "scale_x": 0.8}],
            },
        )

        self.assertEqual(saved["scene_key"], scene.key)
        self.assertEqual(saved["blend_mode"], "natural")
        self.assertEqual(saved["layers"][0]["key"], layer.key)
        histories = list_sticker_compositions(self.user)
        self.assertEqual(histories[0]["result_key"], result.key)
        self.assertEqual(histories[0]["blend_mode"], "natural")
        self.assertEqual(PositionStickerComposition.objects.filter(user=self.user).count(), 1)

    def test_sticker_composition_rejects_unowned_layer(self):
        scene = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/sticker-scenes/scene.png",
            url="https://cdn.example.com/scene.png",
            content_type="image/png",
            size=100,
        )
        result = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/composites/result.png",
            url="https://cdn.example.com/result.png",
            content_type="image/png",
            size=100,
        )
        other = get_user_model().objects.create_user(
            username="other-sticker-user",
            email="other-sticker-user@example.com",
            password="pass1234",
        )
        other_layer = UploadedFileRecord.objects.create(
            user=other,
            key="images/cutouts/other.png",
            url="https://cdn.example.com/other.png",
            content_type="image/png",
            size=100,
        )

        with self.assertRaisesMessage(CutoutError, "图层素材不存在或无权访问"):
            create_sticker_composition(
                self.user,
                {
                    "scene_key": scene.key,
                    "result_key": result.key,
                    "layers": [{"key": other_layer.key}],
                },
            )

    @patch("apps.ai_customer.cutout_services._reference_image_data_url")
    @patch("apps.ai_customer.cutout_services._persist_storyboard_png")
    @patch("apps.ai_customer.cutout_services.submit_ai_image_generation")
    def test_enhance_sticker_composite_uses_seedream_model(self, submit_image, persist_png, reference_data_url):
        source = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/composites/source.png",
            url="https://cdn.example.com/source.png",
            content_type="image/png",
            size=100,
        )
        enhanced = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/storyboards/sticker_fusions/enhanced.png",
            url="https://cdn.example.com/enhanced.png",
            content_type="image/png",
            size=120,
        )
        reference_data_url.return_value = "data:image/png;base64,abc"
        submit_image.return_value = {"status": "completed", "images": ["https://seedream.example.com/fused.png"]}
        persist_png.return_value = enhanced.url

        result = enhance_sticker_composite(self.user, {"composite_key": source.key})

        self.assertEqual(result["key"], enhanced.key)
        self.assertEqual(result["model"], "doubao-seedream-5-0-260128")
        self.assertEqual(submit_image.call_args.kwargs["model"], "doubao-seedream-5-0-260128")
        self.assertIn("不改变画面构图", submit_image.call_args.kwargs["prompt"])
        self.assertEqual(submit_image.call_args.kwargs["reference_images"][0]["data_url"], "data:image/png;base64,abc")
        persist_png.assert_called_once_with(
            "https://seedream.example.com/fused.png",
            self.user,
            "sticker_fusions",
            "doubao-seedream-5-0-260128",
            allow_remote_fallback=False,
        )


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


class OctopusNoteApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="octopus-writer",
            email="octopus-writer@example.com",
            password="pass1234",
            can_access_workbench=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_folder_and_note_crud_flow(self):
        created_folder = self.client.post("/api/v1/octopus-note/folders", {"name": "灵感仓"})
        self.assertEqual(created_folder.status_code, 200)
        folder_id = created_folder.data["data"]["id"]

        renamed_folder = self.client.patch(f"/api/v1/octopus-note/folders/{folder_id}", {"name": "项目灵感"})
        self.assertEqual(renamed_folder.status_code, 200)
        self.assertEqual(renamed_folder.data["data"]["name"], "项目灵感")

        covered_folder = self.client.patch(
            f"/api/v1/octopus-note/folders/{folder_id}",
            {"cover_url": "https://assets.example.com/folder-cover.jpg"},
        )
        self.assertEqual(covered_folder.status_code, 200)
        self.assertEqual(covered_folder.data["data"]["cover_url"], "https://assets.example.com/folder-cover.jpg")

        created_note = self.client.post(f"/api/v1/octopus-note/folders/{folder_id}/notes", {"title": "第一本"})
        self.assertEqual(created_note.status_code, 200)
        note_id = created_note.data["data"]["id"]

        saved_note = self.client.patch(
            f"/api/v1/octopus-note/notes/{note_id}",
            {
                "title": "第一本修订",
                "content": "海底有一束蓝色光",
                "font_family": "Orbitron",
                "font_size": 24,
                "text_color": "#66fff4",
                "cover_url": "https://assets.example.com/note-cover.jpg",
                "image_urls": [f"https://assets.example.com/note-{index}.jpg" for index in range(12)],
            },
            format="json",
        )
        self.assertEqual(saved_note.status_code, 200)
        self.assertEqual(saved_note.data["data"]["content"], "海底有一束蓝色光")
        self.assertEqual(saved_note.data["data"]["font_size"], 24)
        self.assertEqual(saved_note.data["data"]["cover_url"], "https://assets.example.com/note-cover.jpg")
        self.assertEqual(len(saved_note.data["data"]["image_urls"]), 10)
        self.assertEqual(saved_note.data["data"]["image_urls"][0], "https://assets.example.com/note-0.jpg")

        note_list = self.client.get(f"/api/v1/octopus-note/folders/{folder_id}/notes", {"q": "蓝色", "order": "created_asc"})
        self.assertEqual(note_list.status_code, 200)
        self.assertEqual(len(note_list.data["data"]["list"]), 1)

        deleted_note = self.client.delete(f"/api/v1/octopus-note/notes/{note_id}")
        self.assertEqual(deleted_note.status_code, 200)
        self.assertFalse(OctopusNote.objects.filter(id=note_id).exists())

        deleted_folder = self.client.delete(f"/api/v1/octopus-note/folders/{folder_id}")
        self.assertEqual(deleted_folder.status_code, 200)
        self.assertFalse(OctopusNoteFolder.objects.filter(id=folder_id).exists())

    def test_cannot_access_other_users_note(self):
        other = get_user_model().objects.create_user(
            username="other-octopus-writer",
            email="other-octopus-writer@example.com",
            password="pass1234",
            can_access_workbench=True,
        )
        folder = OctopusNoteFolder.objects.create(user=other, name="别人的文件夹")
        note = OctopusNote.objects.create(user=other, folder=folder, title="别人的记事本")

        folder_response = self.client.get(f"/api/v1/octopus-note/folders/{folder.id}/notes")
        note_response = self.client.patch(f"/api/v1/octopus-note/notes/{note.id}", {"title": "不该成功"})

        self.assertEqual(folder_response.status_code, 404)
        self.assertEqual(note_response.status_code, 404)
        note.refresh_from_db()
        self.assertEqual(note.title, "别人的记事本")

    @patch("apps.ai_customer.octopus_planet_services.upsert_qdrant_publish")
    def test_publish_note_to_octopus_planet_and_common_tags(self, upsert_qdrant):
        upsert_qdrant.return_value = True
        folder = OctopusNoteFolder.objects.create(user=self.user, name="星球文件夹")
        note = OctopusNote.objects.create(
            user=self.user,
            folder=folder,
            title="星球记事",
            content="一段准备公开的灵感",
            image_urls=["https://assets.example.com/planet-a.jpg", "https://assets.example.com/planet-b.jpg"],
        )

        too_long = self.client.post(
            "/api/v1/octopus-planet/publish",
            {"notebook_id": note.id, "tag": "超过十个字的标签会失败"},
            format="json",
        )
        self.assertEqual(too_long.status_code, 400)

        added_tag = self.client.post("/api/v1/octopus-planet/my-common-tags", {"tag": "分镜"}, format="json")
        self.assertEqual(added_tag.status_code, 200)
        self.assertEqual(added_tag.data["data"]["tag"], "分镜")

        first = self.client.post(
            "/api/v1/octopus-planet/publish",
            {"notebook_id": note.id, "tags": ["  玄幻  ", "分镜", "AI", "修仙", "角色", "超出"]},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["data"]["is_vector_ready"])
        self.assertEqual(first.data["data"]["tags"], ["玄幻", "分镜", "AI", "修仙", "角色"])
        publish = OctopusPlanetPublish.objects.get(note=note)
        self.assertEqual(publish.tag, "玄幻")
        self.assertEqual(publish.tags, ["玄幻", "分镜", "AI", "修仙", "角色"])
        self.assertEqual(publish.tag_normalized, "玄幻")
        self.assertIsNotNone(publish.particle_x)
        self.assertEqual(OctopusPlanetTagStat.objects.get(user=self.user, tag_normalized="玄幻").use_count, 1)
        self.assertEqual(OctopusPlanetTagStat.objects.get(user=self.user, tag_normalized="分镜").use_count, 1)

        second = self.client.post(
            "/api/v1/octopus-planet/publish",
            {"notebook_id": note.id, "tags": ["玄幻", "AI"]},
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(OctopusPlanetTagStat.objects.get(user=self.user, tag_normalized="玄幻").use_count, 2)

        common = self.client.get("/api/v1/octopus-planet/my-common-tags")
        self.assertEqual(common.status_code, 200)
        common_counts = {item["tag"]: item["use_count"] for item in common.data["data"]["items"]}
        self.assertEqual(common_counts["玄幻"], 2)
        self.assertEqual(common_counts["AI"], 2)
        self.assertEqual(common_counts["分镜"], 1)

        particles = self.client.get("/api/v1/octopus-planet/particles", {"scope": "mine"})
        self.assertEqual(particles.status_code, 200)
        self.assertEqual(len(particles.data["data"]["items"]), 1)
        self.assertTrue(particles.data["data"]["items"][0]["is_mine"])

        search = self.client.get("/api/v1/octopus-planet/search", {"tag": "玄幻", "scope": "mine"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.data["data"]["items"][0]["publish_id"], publish.id)
        self.assertTrue(search.data["data"]["items"][0]["highlight"])

        detail = self.client.get(f"/api/v1/octopus-planet/publish/{publish.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["data"]["title"], "星球记事")
        self.assertEqual(len(detail.data["data"]["image_urls"]), 2)

    def test_octopus_planet_scope_mine_filters_other_users(self):
        folder = OctopusNoteFolder.objects.create(user=self.user, name="我的文件夹")
        note = OctopusNote.objects.create(user=self.user, folder=folder, title="我的记事")
        OctopusPlanetPublish.objects.create(
            note=note,
            user=self.user,
            tag="灵感",
            tag_normalized="灵感",
            qdrant_point_id=str(note.id),
            particle_x=0,
            particle_y=0,
            particle_z=1,
        )
        other = get_user_model().objects.create_user(
            username="planet-other",
            email="planet-other@example.com",
            password="pass1234",
            can_access_workbench=True,
        )
        other_folder = OctopusNoteFolder.objects.create(user=other, name="别人的文件夹")
        other_note = OctopusNote.objects.create(user=other, folder=other_folder, title="别人的记事")
        OctopusPlanetPublish.objects.create(
            note=other_note,
            user=other,
            tag="灵感",
            tag_normalized="灵感",
            qdrant_point_id=str(other_note.id),
            particle_x=0,
            particle_y=1,
            particle_z=0,
        )

        all_particles = self.client.get("/api/v1/octopus-planet/particles", {"scope": "all"})
        mine_particles = self.client.get("/api/v1/octopus-planet/particles", {"scope": "mine"})

        self.assertEqual(len(all_particles.data["data"]["items"]), 2)
        self.assertEqual(len(mine_particles.data["data"]["items"]), 1)
        self.assertEqual(mine_particles.data["data"]["items"][0]["user_id"], self.user.id)


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

    def test_scene_inference_project_delete_removes_owned_history_record(self):
        self.user.can_access_storyboard = True
        self.user.save(update_fields=["can_access_storyboard"])
        client = APIClient()
        client.force_authenticate(self.user)
        project = create_scene_inference_project(
            self.user,
            {
                "front_image_url": "https://assets.example.com/front.png",
                "back_image_url": "https://assets.example.com/back.png",
            },
        )
        SceneInferenceJob.objects.create(project=project, job_type=SceneInferenceJob.TYPE_LEFT)
        other_user = get_user_model().objects.create_user(
            username="other-scene-director",
            email="other-scene-director@example.com",
            password="pass1234",
        )
        other_project = SceneInferenceProject.objects.create(
            user=other_user,
            title="其他人的记录",
            front_image_url="https://assets.example.com/other-front.png",
            back_image_url="https://assets.example.com/other-back.png",
        )

        response = client.delete(f"/api/v1/scene-inference/projects/{project.id}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["deleted"])
        self.assertFalse(SceneInferenceProject.objects.filter(id=project.id).exists())
        self.assertFalse(SceneInferenceJob.objects.filter(project_id=project.id).exists())
        self.assertTrue(SceneInferenceProject.objects.filter(id=other_project.id).exists())

        forbidden = client.delete(f"/api/v1/scene-inference/projects/{other_project.id}")

        self.assertEqual(forbidden.status_code, 404)
        self.assertTrue(SceneInferenceProject.objects.filter(id=other_project.id).exists())

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
        self.assertEqual(
            [item["data_url"] for item in submit_image.call_args_list[0].kwargs["reference_images"]],
            ["data:https://assets.example.com/front.png", "data:https://assets.example.com/back.png"],
        )
        self.assertIn("输入图是唯一事实来源", submit_image.call_args_list[0].kwargs["prompt"])
        self.assertIn("严禁把室外改成室内", submit_image.call_args_list[0].kwargs["prompt"])
        self.assertEqual(reference_data_url.call_count, 6)

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
        self.assertEqual(submit_image.call_args.kwargs["reference_images"][0]["data_url"], "data:https://assets.example.com/front.png")
        self.assertIn("参考图顺序：第 1 张正面图", submit_image.call_args.kwargs["prompt"])

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
        self.assertEqual(submit_image.call_args.kwargs["reference_images"][0]["data_url"], "data:image/png;base64,abc")

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

    @patch("apps.ai_customer.llm_clients.requests.post")
    def test_image_generation_timeout_returns_actionable_message(self, post):
        post.side_effect = Timeout("read timed out")

        with self.assertRaisesMessage(LLMClientError, "生图模型提交超时，请稍后刷新任务或降低参考图尺寸后重试"):
            image_generation(
                "https://api.example.com/v1",
                "sk-test",
                {"model": "gpt-image-2", "prompt": "生成场景图"},
                service_name="生图模型",
            )

    @patch("apps.ai_customer.llm_clients.requests.post")
    def test_image_generation_connection_failure_returns_actionable_message(self, post):
        post.side_effect = ConnectionError("name resolution failed")

        with self.assertRaisesMessage(LLMClientError, "生图模型请求失败：无法连接到模型服务"):
            image_generation(
                "https://api.example.com/v1",
                "sk-test",
                {"model": "gpt-image-2", "prompt": "生成场景图"},
                service_name="生图模型",
            )


class AIImageResultParsingTests(TestCase):
    def test_image_urls_extracts_top_level_images(self):
        result = _image_urls(
            {
                "images": [
                    {"url": "https://upload.apimart.ai/f/image/top-level.png"},
                ],
            }
        )

        self.assertEqual(result, ["https://upload.apimart.ai/f/image/top-level.png"])

    def test_task_result_images_extracts_url_from_stringified_list(self):
        result = _task_result_images(
            {
                "result": {
                    "images": "['https://upload.apimart.ai/f/image/example.png']",
                }
            }
        )

        self.assertEqual(result, ["https://upload.apimart.ai/f/image/example.png"])
