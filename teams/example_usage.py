"""
Пример использования утилитных функций управления командами

Этот файл демонстрирует, как использовать функции из teams/utils.py
для управления жизненным циклом команд.
"""

from django.contrib.auth import get_user_model
from .models import Team, TeamStatus
from .utils import (
    deactivate_team, 
    reactivate_team, 
    disband_team, 
    get_team_status_statistics,
    can_perform_team_action
)

User = get_user_model()


def example_team_lifecycle():
    """
    Пример полного жизненного цикла команды
    """
    # Получаем пользователя (руководителя команды)
    try:
        leader = User.objects.get(username='leader_username')
    except User.DoesNotExist:
        print("Пользователь не найден")
        return
    
    # Получаем команду
    try:
        team = Team.objects.get(name='My Team', creator=leader)
    except Team.DoesNotExist:
        print("Команда не найдена")
        return
    
    print(f"Начальный статус команды: {team.get_status_display()}")
    
    # 1. Приостанавливаем команду
    try:
        can_deactivate, reason = can_perform_team_action(team, leader, 'deactivate')
        if can_deactivate:
            deactivate_team(team, leader, "Временная приостановка для реорганизации")
            print("✓ Команда успешно приостановлена")
        else:
            print(f"✗ Нельзя приостановить команду: {reason}")
    except Exception as e:
        print(f"✗ Ошибка при приостановке: {e}")
    
    # 2. Возобновляем команду
    try:
        can_reactivate, reason = can_perform_team_action(team, leader, 'reactivate')
        if can_reactivate:
            reactivate_team(team, leader, "Реорганизация завершена")
            print("✓ Команда успешно возобновлена")
        else:
            print(f"✗ Нельзя возобновить команду: {reason}")
    except Exception as e:
        print(f"✗ Ошибка при возобновлении: {e}")
    
    # 3. Распускаем команду
    try:
        can_disband, reason = can_perform_team_action(team, leader, 'disband')
        if can_disband:
            disband_team(team, leader, "Проект завершен")
            print("✓ Команда успешно распущена")
        else:
            print(f"✗ Нельзя распустить команду: {reason}")
    except Exception as e:
        print(f"✗ Ошибка при роспуске: {e}")
    
    # 4. Получаем статистику
    stats = get_team_status_statistics(leader)
    print(f"\nСтатистика команд пользователя:")
    print(f"  Активных: {stats['active']}")
    print(f"  Неактивных: {stats['inactive']}")
    print(f"  Распущенных: {stats['disbanded']}")
    print(f"  Всего: {stats['total']}")


def example_permission_check():
    """
    Пример проверки прав доступа
    """
    try:
        leader = User.objects.get(username='leader_username')
        regular_user = User.objects.get(username='regular_user')
        team = Team.objects.get(name='My Team')
    except (User.DoesNotExist, Team.DoesNotExist):
        print("Пользователи или команда не найдены")
        return
    
    # Проверяем права руководителя
    can_manage, reason = can_perform_team_action(team, leader, 'deactivate')
    print(f"Руководитель может управлять командой: {can_manage}")
    
    # Проверяем права обычного пользователя
    can_manage, reason = can_perform_team_action(team, regular_user, 'deactivate')
    print(f"Обычный пользователь может управлять командой: {can_manage}")
    if not can_manage:
        print(f"Причина: {reason}")


def example_error_handling():
    """
    Пример обработки ошибок
    """
    try:
        leader = User.objects.get(username='leader_username')
        team = Team.objects.get(name='My Team')
    except (User.DoesNotExist, Team.DoesNotExist):
        print("Пользователи или команда не найдены")
        return
    
    try:
        # Попытка приостановить уже неактивную команду
        if team.status == TeamStatus.INACTIVE:
            deactivate_team(team, leader, "Повторная приостановка")
    except ValueError as e:
        print(f"Ошибка валидации: {e}")
    except PermissionError as e:
        print(f"Ошибка прав доступа: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")


if __name__ == "__main__":
    print("Примеры использования утилитных функций управления командами")
    print("=" * 60)
    
    print("\n1. Полный жизненный цикл команды:")
    example_team_lifecycle()
    
    print("\n2. Проверка прав доступа:")
    example_permission_check()
    
    print("\n3. Обработка ошибок:")
    example_error_handling()