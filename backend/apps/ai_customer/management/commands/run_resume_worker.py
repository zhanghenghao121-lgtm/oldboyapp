from django.core.management.base import BaseCommand

from apps.ai_customer.resume_tasks import run_worker_loop


class Command(BaseCommand):
    help = "Run resume assistant async worker loop"

    def add_arguments(self, parser):
        parser.add_argument("--poll-interval", type=float, default=1.0)

    def handle(self, *args, **options):
        poll_interval = float(options.get("poll_interval") or 1.0)
        self.stdout.write(self.style.SUCCESS(f"Resume worker started, poll_interval={poll_interval}"))
        run_worker_loop(poll_interval=poll_interval)
