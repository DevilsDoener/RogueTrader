from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial non-superuser portal administrator."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password")

    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"] or getpass("Password: ")
        user_model = get_user_model()
        if user_model.objects.filter(username=username).exists():
            raise CommandError(f"User '{username}' already exists.")
        user = user_model(
            username=username,
            is_portal_admin=True,
            is_staff=False,
            is_superuser=False,
            must_change_password=False,
        )
        validate_password(password, user)
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Created portal administrator '{username}'."))
