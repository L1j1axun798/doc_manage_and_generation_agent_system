from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.webauthn_services import create_enrollment_ticket

User = get_user_model()


class Command(BaseCommand):
    help = "Create a one-time WebAuthn enrollment link for bootstrap or recovery."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the account to bind")
        parser.add_argument(
            "--frontend-origin",
            default="http://localhost:5174",
            help="Frontend origin used to build the registration link",
        )

    def handle(self, *args, **options):
        username = options["username"]
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'User "{username}" does not exist')
        if not user.is_active:
            raise CommandError(f'User "{username}" is inactive')
        if not user.is_system_admin:
            raise CommandError("Bootstrap enrollment tickets are limited to system admins")

        result = create_enrollment_ticket(user=user, actor=None, request=None)
        frontend_origin = str(options["frontend_origin"]).rstrip("/")
        url = f"{frontend_origin}/webauthn/register?ticket={result['token']}"

        self.stdout.write(self.style.SUCCESS("WebAuthn enrollment ticket created."))
        self.stdout.write(f"User: {user.username}")
        self.stdout.write(f"Expires at: {result['expires_at'].isoformat()}")
        self.stdout.write(f"URL: {url}")
