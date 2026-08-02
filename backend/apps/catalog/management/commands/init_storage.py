from django.core.management.base import BaseCommand

from apps.common.storage import ensure_bucket


class Command(BaseCommand):
    help = "Create the object storage bucket if it does not already exist."

    def handle(self, *args, **options):
        name = ensure_bucket()
        self.stdout.write(self.style.SUCCESS(f"Bucket ready: {name}"))