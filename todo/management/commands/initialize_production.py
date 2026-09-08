"""
initialize_production — Django management command
=================================================
Safely initialises the production database on first deployment
(and is safe to re-run on every subsequent deployment).

What it does
------------
1. Creates the Django admin/superuser if one does not already exist
   for the configured DJANGO_SUPERUSER_EMAIL address.
2. Creates the application's required Tag seed records if they do
   not already exist, identified by their unique tag_code.

What it does NOT do
-------------------
- It never overwrites an existing superuser's password.
- It never duplicates Tags.
- It never touches regular application users or todos.
- It never prints the admin password to stdout or logs.

Usage
-----
    python manage.py initialize_production

Required environment variables (production)
-------------------------------------------
    DJANGO_SUPERUSER_EMAIL     Email address for the admin account.
    DJANGO_SUPERUSER_PASSWORD  Password for the admin account.
                               Never hardcode; set in Render dashboard.

The command fails with a clear error message if either variable is
missing or empty. This prevents a misconfigured deployment from
creating an admin account with no password.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from todo.models import Tag


# ---------------------------------------------------------------------------
# Required initial Tag records.
# Source: confirmed from the live local SQLite database on 2026-09-08.
# These are the exact records already present in development; tag_code is
# the unique natural key used by the application for filtering.
# ---------------------------------------------------------------------------
INITIAL_TAGS = [
    {"tag_code": 1, "name": "Urgent"},
    {"tag_code": 2, "name": "Highest Priority"},
    {"tag_code": 3, "name": "Mid Priority"},
    {"tag_code": 4, "name": "Low Priority"},
    {"tag_code": 5, "name": "Someday/Maybe"},
]


class Command(BaseCommand):
    help = (
        "Idempotent production initialisation: creates the admin superuser "
        "and required Tag seed records if they do not already exist."
    )

    def handle(self, *args, **options):
        self.stdout.write("==> Starting production initialisation")

        self._create_superuser()
        self._seed_tags()

        self.stdout.write(self.style.SUCCESS("==> Initialisation complete"))

    # ------------------------------------------------------------------
    # Superuser creation
    # ------------------------------------------------------------------

    def _create_superuser(self):
        User = get_user_model()

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()

        if not email:
            raise CommandError(
                "DJANGO_SUPERUSER_EMAIL environment variable is not set or is empty. "
                "Set it in the Render dashboard before deploying."
            )
        if not password:
            raise CommandError(
                "DJANGO_SUPERUSER_PASSWORD environment variable is not set or is empty. "
                "Set it in the Render dashboard before deploying."
            )

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                f"  Superuser already exists ({email}) — skipping creation."
            )
            return

        # create_superuser uses UserManager.create_superuser which sets
        # is_staff=True, is_superuser=True, is_active=True.
        # USERNAME_FIELD = 'email' on this model; no 'username' field exists.
        User.objects.create_superuser(email=email, password=password)

        # Deliberately do NOT log the password.
        self.stdout.write(
            self.style.SUCCESS(f"  Superuser created: {email}")
        )

    # ------------------------------------------------------------------
    # Tag seed data
    # ------------------------------------------------------------------

    def _seed_tags(self):
        created_count = 0

        for tag_data in INITIAL_TAGS:
            tag, created = Tag.objects.get_or_create(
                tag_code=tag_data["tag_code"],
                defaults={"name": tag_data["name"]},
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Tag created: tag_code={tag.tag_code} name={tag.name}"
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    f"  Tag already exists: tag_code={tag.tag_code} name={tag.name} — skipping."
                )

        if created_count == 0:
            self.stdout.write("  All tags already present — no tags created.")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"  {created_count} tag(s) created.")
            )
