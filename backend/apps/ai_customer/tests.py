from unittest.mock import patch
import io

from django.contrib.auth import get_user_model
from django.test import TestCase
from PIL import Image

from apps.ai_customer.llm_clients import LLMClientError, chat_completion
from apps.ai_customer.ai_image_services import _task_result_images
from apps.ai_customer.models import StoryboardAsset, StoryboardPanel, StoryboardProject, StorySegment
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
                        "title": "站台等待",
                        "scene_name": "火车站台",
                        "time_of_day": "雨夜",
                        "mood": "克制",
                        "summary": "女主在列车到站时看见父亲",
                        "original_text": self.project.original_story,
                        "split_reason": "单一站台场景",
                    }
                ],
            },
            {"can_be_9_grid": True, "score": 91, "reason": "动作连续", "analysis": "一次重逢", "children": []},
            {"characters": [{"name": "林初", "description": "女主"}], "scenes": [], "props": []},
        ]

        result = analyze_project(self.project)

        self.project.refresh_from_db()
        segment = StorySegment.objects.get(project=self.project)
        self.assertEqual(self.project.title, "雨夜重逢")
        self.assertTrue(segment.is_leaf)
        self.assertEqual(segment.grid_feasibility_score, 91)
        self.assertEqual(segment.required_assets_json["characters"][0]["name"], "林初")
        self.assertEqual(segment.assets.get().name, "林初")
        self.assertEqual(segment.assets.get().image_url, "")
        self.assertEqual(len(result["segments"]), 1)

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
