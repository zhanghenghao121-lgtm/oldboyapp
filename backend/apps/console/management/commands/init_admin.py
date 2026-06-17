import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Initialize default admin account if it does not exist"

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = os.getenv("ADMIN_INIT_USERNAME", "root").strip() or "root"
        password = os.getenv("ADMIN_INIT_PASSWORD", "zhang2000")
        email = os.getenv("ADMIN_INIT_EMAIL", "root@oldboyai.com").strip().lower() or "root@oldboyai.com"

        user = user_model.objects.filter(username=username).first()
        if user:
            changed = False
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.can_access_workbench:
                user.can_access_workbench = True
                changed = True
            if not user.can_access_storyboard:
                user.can_access_storyboard = True
                changed = True
            if changed:
                user.save(update_fields=["is_staff", "is_superuser", "can_access_workbench", "can_access_storyboard"])
                self.stdout.write(self.style.SUCCESS(f"Updated admin permissions for '{username}'"))
            else:
                self.stdout.write(f"Admin '{username}' already exists")
            return

        user = user_model.objects.create_superuser(username=username, email=email, password=password)
        user.can_access_workbench = True
        user.can_access_storyboard = True
        user.save(update_fields=["can_access_workbench", "can_access_storyboard"])
        self.stdout.write(self.style.SUCCESS(f"Created admin '{username}'"))
