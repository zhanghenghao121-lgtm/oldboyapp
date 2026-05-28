from unittest.mock import patch
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.storage.models import UploadedFileRecord


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
