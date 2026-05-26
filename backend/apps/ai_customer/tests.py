from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai_customer.models import StoryboardProject, StorySegment
from apps.ai_customer.storyboard_services import analyze_project, generate_panels


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
            {"characters": [{"name": "林初", "description": "女主"}], "scenes": [], "props": [], "costumes": [], "style_refs": []},
        ]

        result = analyze_project(self.project)

        self.project.refresh_from_db()
        segment = StorySegment.objects.get(project=self.project)
        self.assertEqual(self.project.title, "雨夜重逢")
        self.assertTrue(segment.is_leaf)
        self.assertEqual(segment.grid_feasibility_score, 91)
        self.assertEqual(segment.required_assets_json["characters"][0]["name"], "林初")
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
