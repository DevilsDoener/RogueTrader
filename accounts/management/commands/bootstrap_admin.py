from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts import usernames
from accounts.services import audit_logger


class Command(BaseCommand):
    help = "Create the initial non-superuser portal administrator."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password")

    def handle(self, *args, **options):
        password = options["password"] or getpass("Password: ")
        user_model = get_user_model()
        try:
            username = usernames.clean_username(options["username"])
        except ValidationError as error:
            if error.code == "unique":
                raise CommandError(f"User '{options['username'].strip()}' already exists.") from error
            raise CommandError("; ".join(error.messages)) from error
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
        audit_logger.info("bootstrap_admin_created username=%r", username)
        self.stdout.write(self.style.SUCCESS(f"Created portal administrator '{username}'."))
