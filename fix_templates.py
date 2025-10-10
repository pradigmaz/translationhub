#!/usr/bin/env python
"""
Скрипт для исправления проблем с отображением Django templates
"""
import os
import sys
import django
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

def main():
    print("🔧 Исправление проблем с отображением карточек команд...")
    
    # Проверка Django
    print("✅ Django настроен корректно")
    print(f"   DEBUG: {settings.DEBUG}")
    
    # Проверка базы данных
    from teams.models import Team
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    teams_count = Team.objects.count()
    users_count = User.objects.count()
    
    print(f"✅ База данных доступна")
    print(f"   Команд: {teams_count}")
    print(f"   Пользователей: {users_count}")
    
    # Проверка template engine
    from django.template import Template, Context
    template = Template("Тест: {{ name }}")
    result = template.render(Context({'name': 'OK'}))
    print(f"✅ Template engine работает: {result}")
    
    # Инструкции для пользователя
    print("\n📋 Инструкции по исправлению:")
    print("1. Убедитесь, что вы вошли в систему (/accounts/login/)")
    print("2. Очистите кэш браузера (Ctrl+Shift+R)")
    print("3. Откройте /teams/ через Django сервер (не как файл)")
    print("4. Проверьте тестовую страницу: /test-django/")
    
    print("\n🚀 Запуск сервера разработки...")
    print("   Откройте: http://127.0.0.1:8000/teams/")
    print("   Для остановки нажмите Ctrl+C")
    
    # Запуск сервера
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'runserver', '127.0.0.1:8000'])

if __name__ == "__main__":
    main()