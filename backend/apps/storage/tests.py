from unittest.mock import patch
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.storage.models import UploadedFileRecord
from apps.ai_customer.models import StoryboardPanel, StoryboardProject, StorySegment


@override_settings(
    COS_SECRET_ID="id",
    COS_SECRET_KEY="key",
    COS_BUCKET="bucket",
    COS_REGION="ap-test",
    COS_BASE_URL="https://assets.example.com",
    MAX_UPLOAD_SIZE=10 * 1024 * 1024,
    IMAGE_SOURCE_MAX_UPLOAD_SIZE=80 * 1024 * 1024,
)
class UploadCompressionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="uploader", password="pass1234")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("apps.storage.views.CosS3Client.put_object")
    @patch("apps.storage.views._compress_image_bytes")
    def test_large_image_is_compressed_before_final_size_validation(self, compress, put_object):
        compress.return_value = (b"compressed-image", "image/jpeg", ".jpg")
        large_image = SimpleUploadedFile(
            "storyboard.png",
            b"x" * (15 * 1024 * 1024 + 1),
            content_type="image/png",
        )

        response = self.client.post(
            "/api/v1/storage/upload",
            {"file": large_image, "folder": "images/storyboards/assets"},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["data"]["size"], len(b"compressed-image"))
        compress.assert_called_once()
        put_object.assert_called_once()

    @patch("apps.storage.views.CosS3Client.get_object")
    def test_file_endpoint_returns_owned_cos_bytes(self, get_object):
        record = UploadedFileRecord.objects.create(
            user=self.user,
            key="images/storyboards/panels/2026/05/28/panel.png",
            url="https://assets.example.com/images/storyboards/panels/2026/05/28/panel.png",
            content_type="image/png",
            size=7,
        )
        get_object.return_value = {"Body": type("Body", (), {"get_raw_stream": lambda self: io.BytesIO(b"pngdata")})()}

        response = self.client.get("/api/v1/storage/file", {"url": record.url, "download": "1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content, b"pngdata")

    @patch("apps.storage.views.requests.get")
    def test_file_endpoint_extracts_real_url_from_malformed_storyboard_url(self, get):
        project = StoryboardProject.objects.create(user=self.user, title="故事板", original_story="一段足够长的测试剧情内容")
        segment = StorySegment.objects.create(project=project, title="片段", is_leaf=True)
        malformed = "https://api.apimart.ai/v1/['https://upload.apimart.ai/f/image/example.png']"
        StoryboardPanel.objects.create(segment=segment, panel_no=1, image_url=malformed)
        image_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        bad_response = type("Response", (), {"raise_for_status": lambda self: (_ for _ in ()).throw(Exception("bad url"))})()
        good_response = type(
            "Response",
            (),
            {
                "content": image_bytes,
                "headers": {"Content-Type": "image/png"},
                "raise_for_status": lambda self: None,
            },
        )()
        get.side_effect = [bad_response, bad_response, good_response]

        response = self.client.get("/api/v1/storage/file", {"url": malformed})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, image_bytes)
