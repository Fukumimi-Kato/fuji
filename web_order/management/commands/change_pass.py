from django.core.management.base import BaseCommand
from accounts.models import User

class Command(BaseCommand):
    def handle(self, *args, **options):

        '''
        user = User.objects.filter(username='10032')
        user.set_password('dan' + str(user.username))
        user.save()
        '''

        users = User.objects.all()
        for user in users:
            user.set_password(str(user.username))
            user.save()
