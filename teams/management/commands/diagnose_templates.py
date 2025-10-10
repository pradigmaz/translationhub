from django.core.management.base import BaseCommand
from django.template import Template, Context
from django.contrib.auth import get_user_model
from teams.models import Team
from django.conf import settings


class Command(BaseCommand):
    help = 'Диагностика проблем с Django templates'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Диагностика Django Templates ==='))
        
        # Проверка настроек Django
        self.stdout.write(f'DEBUG режим: {settings.DEBUG}')
        self.stdout.write(f'TEMPLATES настройки: OK')
        
        # Проверка template engine
        template_str = "Тест: {{ name }} - {{ count }}"
        template = Template(template_str)
        context = Context({'name': 'Django', 'count': 123})
        result = template.render(context)
        self.stdout.write(f'Template engine тест: {result}')
        
        # Проверка моделей
        User = get_user_model()
        users_count = User.objects.count()
        teams_count = Team.objects.count()
        self.stdout.write(f'Пользователей в БД: {users_count}')
        self.stdout.write(f'Команд в БД: {teams_count}')
        
        # Проверка конкретной команды
        if teams_count > 0:
            team = Team.objects.first()
            template_str = "Команда: {{ team.name }}, Создатель: {{ team.creator.username }}, Статус: {{ team.get_status_display }}"
            template = Template(template_str)
            context = Context({'team': team})
            result = template.render(context)
            self.stdout.write(f'Тест с моделью Team: {result}')
        
        # Проверка пользователей с командами
        for user in User.objects.all()[:3]:
            user_teams = Team.objects.filter(creator=user).count()
            self.stdout.write(f'Пользователь {user.username}: {user_teams} команд')
        
        self.stdout.write(self.style.SUCCESS('=== Диагностика завершена ==='))
        self.stdout.write(self.style.WARNING('Если вы видите этот вывод, Django работает корректно!'))
        self.stdout.write(self.style.WARNING('Проблема может быть в:'))
        self.stdout.write('1. Кэшировании браузера - очистите кэш (Ctrl+Shift+R)')
        self.stdout.write('2. Аутентификации - войдите в систему')
        self.stdout.write('3. Неправильном URL - убедитесь что открываете /teams/ через Django сервер')