from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings


@override_settings(
    EMAIL_CODE_IP_LIMIT_PER_MINUTE=10,
    EMAIL_CODE_DAILY_LIMIT=10,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class EmailCodeRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        User.objects.create_user(username="alpha", email="alpha@example.com", password="Pass1234A")
        User.objects.create_user(username="bravo", email="bravo@example.com", password="Pass1234A")
        self.client = Client()

    @patch("apps.accounts.views.send_mail", return_value=1)
    def test_same_ip_can_send_reset_codes_to_different_emails(self, send_mail):
        first = self.client.post(
            "/api/v1/auth/email-code",
            {"email": "alpha@example.com", "scene": "reset"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="203.0.113.10",
        )
        second = self.client.post(
            "/api/v1/auth/email-code",
            {"email": "bravo@example.com", "scene": "reset"},
            content_type="application/json",
            HTTP_X_FORWARDED_FOR="203.0.113.10",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(send_mail.call_count, 2)

    @patch("apps.accounts.views.send_mail", return_value=1)
    def test_same_email_still_has_sixty_second_cooldown(self, send_mail):
        first = self.client.post(
            "/api/v1/auth/email-code",
            {"email": "alpha@example.com", "scene": "reset"},
            content_type="application/json",
        )
        second = self.client.post(
            "/api/v1/auth/email-code",
            {"email": "alpha@example.com", "scene": "reset"},
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(send_mail.call_count, 1)

    @patch("apps.accounts.views.send_mail", side_effect=RuntimeError("smtp unavailable"))
    def test_email_send_failure_returns_json_error(self, send_mail):
        response = self.client.post(
            "/api/v1/auth/email-code",
            {"email": "alpha@example.com", "scene": "reset"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["ok"], False)
        self.assertIn("验证码邮件发送失败", response.json()["message"])
        self.assertEqual(send_mail.call_count, 1)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AccountPermissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_new_user_feature_permissions_default_off(self):
        User = get_user_model()
        user = User.objects.create_user(username="newbie", email="newbie@example.com", password="Pass1234A")

        self.assertFalse(user.can_access_workbench)
        self.assertFalse(user.can_access_storyboard)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_inactive_user_login_returns_account_status_error(self):
        User = get_user_model()
        User.objects.create_user(
            username="inactive",
            email="inactive@example.com",
            password="Pass1234A",
            is_active=False,
        )

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "inactive", "password": "Pass1234A"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("账号状态异常", response.json()["message"])

    def test_admin_frontend_permissions_are_always_enabled(self):
        User = get_user_model()
        User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="Pass1234A",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "admin", "password": "Pass1234A"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        user = response.json()["data"]["user"]
        self.assertTrue(user["can_access_workbench"])
        self.assertTrue(user["can_access_storyboard"])

    def test_normal_user_cannot_login_console(self):
        User = get_user_model()
        User.objects.create_user(username="plain", email="plain@example.com", password="Pass1234A")

        response = self.client.post(
            "/api/v1/console/login",
            {"username": "plain", "password": "Pass1234A"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("无后台访问权限", response.json()["message"])
