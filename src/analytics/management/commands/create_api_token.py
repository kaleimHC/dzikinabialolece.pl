"""
Management command: create or retrieve a DRF Token for a given user.

Usage:
    python manage.py create_api_token --username <username>
    python manage.py create_api_token --username admin --create-superuser
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Create (or retrieve) a DRF API token for a user and print it.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Username')
        parser.add_argument('--create-superuser', action='store_true',
                            help='Create superuser if it does not exist')
        parser.add_argument('--password', default='changeme',
                            help='Password for --create-superuser (default: changeme)')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']

        if options['create_superuser']:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'is_staff': True, 'is_superuser': True}
            )
            if created:
                user.set_password(options['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Superuser {username!r} created.'))
            else:
                self.stdout.write(f'User {username!r} already exists.')
        else:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(
                    f'User "{username}" does not exist. '
                    f'Use --create-superuser to create one.'
                )

        token, created = Token.objects.get_or_create(user=user)
        verb = 'Created' if created else 'Existing'
        self.stdout.write(self.style.SUCCESS(f'\n{verb} token for {username!r}:'))
        self.stdout.write(f'  {token.key}\n')
        self.stdout.write('Usage:')
        self.stdout.write(f'  curl -H "Authorization: Token {token.key}" \\')
        self.stdout.write(f'       -X POST https://dzikinabialolece.pl/api/research/run/')
