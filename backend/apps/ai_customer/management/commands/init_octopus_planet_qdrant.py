from django.core.management.base import BaseCommand

from apps.ai_customer.octopus_planet_services import embedding_text, ensure_qdrant_collection


class Command(BaseCommand):
    help = "Initialize the Qdrant collection used by Octopus Planet."

    def handle(self, *args, **options):
        vector = embedding_text("测试")
        ok = ensure_qdrant_collection(len(vector))
        if ok:
            self.stdout.write(self.style.SUCCESS("Octopus Planet Qdrant collection is ready."))
        else:
            self.stdout.write(self.style.WARNING("Qdrant is not configured or cannot be reached."))
