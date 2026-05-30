from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings


@override_settings(EMAIL_CODE_IP_LIMIT_PER_MINUTE=10, EMAIL_CODE_DAILY_LIMIT=10)
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
