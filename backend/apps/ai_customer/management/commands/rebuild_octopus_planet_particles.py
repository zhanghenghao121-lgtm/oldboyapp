from django.core.management.base import BaseCommand
from django.db import OperationalError, ProgrammingError

from apps.ai_customer.octopus_planet_services import rebuild_particle_positions


class Command(BaseCommand):
    help = "Rebuild cached 3D particle positions for Octopus Planet publishes."

    def handle(self, *args, **options):
        try:
            count = rebuild_particle_positions()
        except (OperationalError, ProgrammingError):
            self.stdout.write(self.style.WARNING("Octopus Planet tables are not ready. Run migrations first."))
            return
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {count} Octopus Planet particles."))
