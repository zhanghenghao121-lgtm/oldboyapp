import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.console.models import SiteConfig
from apps.ai_script_breakdown.duration_engine import load_dialogue_duration_config, prepare_shot_lines
from apps.ai_script_breakdown.models import AiScriptAsset, AiScriptBreakdownProject, AiScriptSceneBlock, AiScriptShotSegment
from apps.ai_script_breakdown.prompts import DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT
from apps.ai_script_breakdown.services import (
    ScriptBreakdownError,
    create_project,
    generate_position_image,
    run_project,
    update_asset,
    _save_scene_segments,
)


class AiScriptBreakdownServicesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="script-director", password="pass1234")
        self.script_text = (
            "1-1 龙吟堂 日。执事推开龙吟堂大门，众人从供桌旁退开。"
            "主角发现地上的灰烬呈现奇怪符号，低声询问来历。"
            "长老解释昨夜祭坛忽然熄灭，守夜弟子全部失踪。"
            "门外传来钟声，另一名弟子跌跌撞撞冲入堂内。"
        )

    @patch("apps.ai_script_breakdown.services._call_script_json")
    def test_run_project_creates_scene_blocks_and_15s_segments(self, call_model):
        call_model.side_effect = [
            {
                "scenes": [{"name": "龙吟堂", "description": "山门正殿", "matched_uploaded_asset_name": "龙吟堂参考图"}],
                "characters": [{"name": "主角", "description": "查案者", "matched_uploaded_asset_name": ""}],
                "props": [{"name": "灰烬符号", "description": "关键线索", "matched_uploaded_asset_name": ""}],
            },
            {
                "scene_blocks": [
                    {
                        "scene_number": "1-1",
                        "scene_name": "龙吟堂覆灭余波",
                        "location": "龙吟堂",
                        "time_of_day": "日",
                        "scene_description": "众人在正殿发现异常线索。",
                        "front_view_description": "镜头面向供桌和主角。",
                        "reverse_view_description": "从供桌方向反打众人。",
                        "original_text": self.script_text,
                        "characters": ["主角", "长老", "弟子"],
                        "props": ["灰烬符号"],
                        "order_index": 1,
                    }
                ]
            },
            {
                "segments": [
                    {
                        "segment_title": "发现灰烬",
                        "estimated_duration": 12,
                        "scene_view": "front",
                        "continuity_from_previous": False,
                        "shot_lines": [
                            {
                                "shot_size": "全景",
                                "description": "执事推开龙吟堂大门，众人从供桌旁退开。",
                                "dialogue": "",
                                "line_text": "【全景】【执事推开龙吟堂大门，众人从供桌旁退开】",
                                "is_continuity_anchor": False,
                            },
                            {
                                "shot_size": "近景",
                                "description": "主角发现地上的灰烬呈现奇怪符号，低声询问来历。",
                                "dialogue": "这是什么？",
                                "line_text": "【近景】【主角发现地上的灰烬呈现奇怪符号，低声说“这是什么？”】",
                                "is_continuity_anchor": False,
                            },
                        ],
                        "copy_text": "",
                        "position_layout": {
                            "scene": "龙吟堂",
                            "view": "front",
                            "camera": {"position": "门口", "direction": "供桌"},
                            "characters": [{"name": "主角", "x": 45, "y": 62, "facing": "供桌", "pose": "俯身"}],
                            "props": [{"name": "灰烬符号", "x": 48, "y": 66, "holder": "", "state": "地面"}],
                        },
                        "position_image_prompt": "龙吟堂内，主角俯身查看灰烬符号。",
                    },
                    {
                        "segment_title": "弟子突入",
                        "estimated_duration": 15,
                        "scene_view": "reverse",
                        "continuity_from_previous": True,
                        "previous_anchor_line": "",
                        "shot_lines": [
                            {
                                "shot_size": "中景",
                                "description": "门外传来钟声，弟子跌跌撞撞冲入堂内。",
                                "dialogue": "后山有黑影！",
                                "line_text": "【中景】【门外传来钟声，弟子跌跌撞撞冲入堂内喊“后山有黑影！”】",
                                "is_continuity_anchor": False,
                            }
                        ],
                        "copy_text": "",
                        "position_layout": {"scene": "龙吟堂", "view": "reverse", "characters": [], "props": []},
                        "position_image_prompt": "龙吟堂反打，弟子从门口冲入。",
                    },
                ]
            },
            {"valid": True, "errors": [], "fixed_json": None},
        ]
        project = create_project(
            self.user,
            {
                "title": "龙吟堂拆剧",
                "script_text": self.script_text,
                "selected_style": AiScriptBreakdownProject.STYLE_LIVE_ACTION,
                "assets": [{"asset_type": AiScriptAsset.TYPE_SCENE, "name": "龙吟堂参考图", "file_url": "https://example.com/scene.png"}],
            },
        )

        result = run_project(project)

        project.refresh_from_db()
        scene = AiScriptSceneBlock.objects.get(project=project)
        segments = list(AiScriptShotSegment.objects.filter(project=project).order_by("order_index"))
        self.assertEqual(project.status, AiScriptBreakdownProject.STATUS_COMPLETED)
        self.assertEqual(scene.scene_number, "1-1")
        self.assertEqual(scene.location, "龙吟堂")
        self.assertEqual(scene.time_of_day, "日")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].estimated_duration, 4)
        self.assertEqual(segments[1].estimated_duration, 3)
        self.assertTrue(segments[0].copy_text.startswith(DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT))
        self.assertIn("【近景】【主角发现地上的灰烬", segments[0].copy_text)
        self.assertIn("【1.4秒】", segments[0].copy_text)
        self.assertEqual(segments[1].previous_anchor_line, "【近景】【主角发现地上的灰烬呈现奇怪符号，低声说“这是什么？”】【1.4秒】")
        self.assertIn(segments[1].previous_anchor_line, segments[1].copy_text)
        self.assertIn("【中景】【门外传来钟声", segments[1].copy_text)
        self.assertEqual(segments[0].position_layout_json, {})
        self.assertEqual(segments[0].position_image_prompt, "")
        self.assertEqual(result["scene_blocks"][0]["scene_number"], "1-1")
        self.assertEqual(result["scene_blocks"][0]["segments"][1]["continuity_from_previous"], True)

    @patch("apps.ai_script_breakdown.services._persist_storyboard_png", return_value="https://assets.example.com/position.png")
    @patch("apps.ai_script_breakdown.services._reference_image_data_url", return_value="data:image/png;base64,xxx")
    @patch("apps.ai_script_breakdown.services.submit_ai_image_generation")
    def test_generate_position_image_uses_uploaded_assets_and_user_description(self, submit_image, reference_data_url, persist_png):
        submit_image.return_value = {"task_id": "task-1", "status": "completed", "images": ["https://remote.example.com/position.png"]}
        project = create_project(self.user, {"title": "站位图样例", "script_text": self.script_text})
        asset = AiScriptAsset.objects.create(project=project, asset_type=AiScriptAsset.TYPE_CHARACTER, name="主角")
        update_asset(asset, {"file_url": "https://assets.example.com/hero.png"})
        scene = AiScriptSceneBlock.objects.create(project=project, scene_name="龙吟堂", location="龙吟堂", characters=["主角"])
        segment = AiScriptShotSegment.objects.create(
            project=project,
            scene_block=scene,
            segment_title="发现灰烬",
            copy_text="真人写实电影质感\n【中景】【主角看向地面灰烬】",
            characters=["主角"],
            props=["灰烬符号"],
        )

        result = generate_position_image(
            segment,
            {"description": "@主角 站在龙吟堂左侧，低头看向地面灰烬，镜头从门口拍摄。", "model": "gpt-image-2"},
        )

        segment.refresh_from_db()
        self.assertEqual(segment.position_description, "@主角 站在龙吟堂左侧，低头看向地面灰烬，镜头从门口拍摄。")
        self.assertEqual(segment.position_image_model, "gpt-image-2")
        self.assertEqual(segment.position_generation_task_id, "task-1")
        self.assertEqual(segment.position_image_url, "https://assets.example.com/position.png")
        self.assertEqual(segment.position_reference_asset_ids, [asset.id])
        self.assertIn("@主角", segment.position_image_prompt)
        self.assertEqual(result["position_image_url"], "https://assets.example.com/position.png")
        self.assertEqual(result["position_reference_asset_ids"], [asset.id])
        self.assertEqual(submit_image.call_args.kwargs["reference_images"][0]["name"], "主角")
        reference_data_url.assert_called_once()
        persist_png.assert_called_once()

    @patch("apps.ai_script_breakdown.services._persist_storyboard_png", return_value="https://assets.example.com/position.png")
    @patch("apps.ai_script_breakdown.services._reference_image_data_url", return_value="data:image/png;base64,xxx")
    @patch("apps.ai_script_breakdown.services.submit_ai_image_generation")
    def test_generate_position_image_uses_explicit_asset_ids_from_mention_cards(self, submit_image, reference_data_url, persist_png):
        submit_image.return_value = {"task_id": "task-2", "status": "completed", "images": ["https://remote.example.com/position.png"]}
        project = create_project(self.user, {"title": "显式引用素材", "script_text": self.script_text})
        chosen = AiScriptAsset.objects.create(
            project=project,
            asset_type=AiScriptAsset.TYPE_SCENE,
            name="龙吟堂",
            file_url="https://assets.example.com/scene.png",
        )
        AiScriptAsset.objects.create(
            project=project,
            asset_type=AiScriptAsset.TYPE_PROP,
            name="未选择道具",
            file_url="https://assets.example.com/prop.png",
        )
        scene = AiScriptSceneBlock.objects.create(project=project, scene_name="龙吟堂")
        segment = AiScriptShotSegment.objects.create(project=project, scene_block=scene, segment_title="站位")

        result = generate_position_image(segment, {"description": "参考所选图片安排开场站位", "asset_ids": [chosen.id]})

        self.assertEqual(result["position_reference_asset_ids"], [chosen.id])
        self.assertEqual([item["name"] for item in submit_image.call_args.kwargs["reference_images"]], ["龙吟堂"])

    @patch("apps.ai_script_breakdown.services._call_script_json")
    def test_run_project_persists_failed_status_when_model_result_is_invalid(self, call_model):
        call_model.side_effect = [
            {"scenes": [], "characters": [], "props": []},
            {"scene_blocks": []},
        ]
        project = create_project(self.user, {"title": "失败样例", "script_text": self.script_text})

        with self.assertRaises(ScriptBreakdownError):
            run_project(project)

        project.refresh_from_db()
        self.assertEqual(project.status, AiScriptBreakdownProject.STATUS_FAILED)
        self.assertIn("模型未返回可用的场景大段落", project.error_message)

    def test_save_scene_segments_uses_backend_duration_config_and_splits_over_limit(self):
        SiteConfig.objects.update_or_create(
            key="ai_script_dialogue_duration_config",
            defaults={
                "value": json.dumps(
                    {
                        "base": {"zh_chars_per_second": 1, "min_dialogue_seconds": 0.1, "non_dialogue_line_seconds": 1.2},
                        "punctuation_pauses": {"。": 0},
                        "action_durations": {"none": 0, "fallback": 0},
                        "pause": {"needed_seconds": 0, "not_needed_seconds": 0},
                    },
                    ensure_ascii=False,
                )
            },
        )
        project = create_project(self.user, {"title": "规则时长拆分", "script_text": self.script_text})
        scene = AiScriptSceneBlock.objects.create(project=project, scene_name="龙吟堂")
        data = {
            "segments": [
                {
                    "segment_title": "长台词段落",
                    "estimated_duration": 1,
                    "shot_lines": [
                        {
                            "shot_size": "近景",
                            "description": "主角说“天地玄黄宇宙洪荒日月盈昃”。",
                            "dialogue": "天地玄黄宇宙洪荒日月盈昃",
                            "character": "主角",
                            "emotion": "neutral",
                            "speech_speed": "normal",
                            "action": "none",
                            "needs_pause": False,
                            "line_text": "【近景】【主角说“天地玄黄宇宙洪荒日月盈昃”。】",
                        },
                        {
                            "shot_size": "近景",
                            "description": "长老说“辰宿列张寒来暑往秋收冬藏”。",
                            "dialogue": "辰宿列张寒来暑往秋收冬藏",
                            "character": "长老",
                            "emotion": "neutral",
                            "speech_speed": "normal",
                            "action": "none",
                            "needs_pause": False,
                            "line_text": "【近景】【长老说“辰宿列张寒来暑往秋收冬藏”。】",
                        },
                    ],
                }
            ]
        }

        _save_scene_segments(scene, data, DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT)

        segments = list(AiScriptShotSegment.objects.filter(project=project).order_by("order_index"))
        self.assertEqual(len(segments), 2)
        self.assertEqual([segment.estimated_duration for segment in segments], [12, 12])
        self.assertIn("【12秒】", segments[0].copy_text)
        self.assertLessEqual(max(segment.estimated_duration for segment in segments), project.max_segment_seconds)

    def test_dialogue_duration_is_added_only_to_speaking_lines(self):
        lines = prepare_shot_lines(
            [
                {
                    "shot_size": "近景",
                    "description": "主角低声说：这是什么？",
                    "character": "主角",
                    "dialogue": "",
                    "line_text": "",
                },
                {
                    "shot_size": "全景",
                    "description": "众人从供桌旁退开，镜头缓慢推进。",
                    "dialogue": "",
                    "line_text": "",
                },
            ],
            load_dialogue_duration_config(),
        )

        self.assertEqual(lines[0]["dialogue"], "这是什么？")
        self.assertRegex(lines[0]["line_text"], r"【近景】【主角低声说：这是什么？】【\d+(?:\.\d)?秒】")
        self.assertEqual(lines[1]["line_text"], "【全景】【众人从供桌旁退开，镜头缓慢推进。】")


class AiScriptBreakdownAssetApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asset-owner",
            email="asset-owner@example.com",
            password="pass1234",
            is_whitelisted=True,
        )
        self.other_user = get_user_model().objects.create_user(
            username="asset-other",
            email="asset-other@example.com",
            password="pass1234",
            is_whitelisted=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = AiScriptBreakdownProject.objects.create(
            user=self.user,
            title="素材删除",
            script_text="一段足够长的剧本内容，用于测试删除解析出来的角色、场景和道具。",
        )

    def test_delete_owned_asset(self):
        asset = AiScriptAsset.objects.create(project=self.project, asset_type=AiScriptAsset.TYPE_CHARACTER, name="主角")

        response = self.client.delete(f"/api/v1/ai-script-breakdown/assets/{asset.id}")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(AiScriptAsset.objects.filter(id=asset.id).exists())

    def test_create_reference_asset(self):
        response = self.client.post(
            f"/api/v1/ai-script-breakdown/projects/{self.project.id}/assets",
            {"asset_type": AiScriptAsset.TYPE_REFERENCE, "name": "走位参考", "file_url": "https://assets.example.com/ref.png"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["asset_type"], AiScriptAsset.TYPE_REFERENCE)
        self.assertTrue(AiScriptAsset.objects.filter(project=self.project, asset_type=AiScriptAsset.TYPE_REFERENCE).exists())

    def test_cannot_delete_other_users_asset(self):
        other_project = AiScriptBreakdownProject.objects.create(
            user=self.other_user,
            title="他人素材",
            script_text="另一段足够长的剧本内容，用于测试不能删除他人的解析素材。",
        )
        asset = AiScriptAsset.objects.create(project=other_project, asset_type=AiScriptAsset.TYPE_PROP, name="令牌")

        response = self.client.delete(f"/api/v1/ai-script-breakdown/assets/{asset.id}")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(AiScriptAsset.objects.filter(id=asset.id).exists())
