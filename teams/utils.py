"""
Утилитные функции для управления жизненным циклом команд
"""

from django.db import transaction
from django.contrib.auth import get_user_model
import logging

from .models import Team, TeamMembership, TeamStatusHistory, TeamStatus, TeamStatusChangeType

logger = logging.getLogger(__name__)
User = get_user_model()


@transaction.atomic
def deactivate_team(team, user, reason=""):
    """
    Приостанавливает работу команды
    
    Args:
        team: Объект команды
        user: Пользователь, выполняющий действие
        reason: Причина приостановки
    
    Returns:
        bool: True если операция успешна
    
    Raises:
        PermissionError: Если пользователь не имеет прав
        ValueError: Если команда не может быть приостановлена
    """
    if not team.can_be_managed_by(user):
        logger.warning(f"Пользователь {user.username} попытался приостановить команду {team.name} без прав")
        raise PermissionError("Недостаточно прав для управления командой")
    
    if team.status != TeamStatus.ACTIVE:
        logger.warning(f"Попытка приостановить команду {team.name} со статусом {team.status}")
        raise ValueError("Можно приостановить только активную команду")
    
    old_status = team.status
    team.status = TeamStatus.INACTIVE
    team.save()
    
    # Записываем в историю
    TeamStatusHistory.objects.create(
        team=team,
        changed_by=user,
        change_type=TeamStatusChangeType.DEACTIVATED,
        old_status=old_status,
        new_status=team.status,
        reason=reason
    )
    
    logger.info(f"Команда {team.name} приостановлена пользователем {user.username}. Причина: {reason}")
    
    # Отправляем уведомления участникам команды
    try:
        from notifications.services import NotificationService
        NotificationService.send_team_status_notification(
            team=team,
            change_type=TeamStatusChangeType.DEACTIVATED,
            changed_by=user,
            reason=reason
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о приостановке команды {team.name}: {e}")
    
    return True


@transaction.atomic
def reactivate_team(team, user, reason=""):
    """
    Возобновляет работу команды
    
    Args:
        team: Объект команды
        user: Пользователь, выполняющий действие
        reason: Причина возобновления
    
    Returns:
        bool: True если операция успешна
    
    Raises:
        PermissionError: Если пользователь не имеет прав
        ValueError: Если команда не может быть возобновлена
    """
    if not team.can_be_managed_by(user):
        logger.warning(f"Пользователь {user.username} попытался возобновить команду {team.name} без прав")
        raise PermissionError("Недостаточно прав для управления командой")
    
    if team.status != TeamStatus.INACTIVE:
        logger.warning(f"Попытка возобновить команду {team.name} со статусом {team.status}")
        raise ValueError("Можно возобновить только приостановленную команду")
    
    old_status = team.status
    team.status = TeamStatus.ACTIVE
    team.save()
    
    # Реактивируем всех участников
    reactivated_count = TeamMembership.objects.filter(team=team).update(is_active=True)
    
    # Записываем в историю
    TeamStatusHistory.objects.create(
        team=team,
        changed_by=user,
        change_type=TeamStatusChangeType.REACTIVATED,
        old_status=old_status,
        new_status=team.status,
        reason=reason
    )
    
    logger.info(f"Команда {team.name} возобновлена пользователем {user.username}. "
                f"Реактивировано участников: {reactivated_count}. Причина: {reason}")
    
    # Отправляем уведомления участникам команды
    try:
        from notifications.services import NotificationService
        NotificationService.send_team_status_notification(
            team=team,
            change_type=TeamStatusChangeType.REACTIVATED,
            changed_by=user,
            reason=reason
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о возобновлении команды {team.name}: {e}")
    
    return True


@transaction.atomic
def disband_team(team, user, reason=""):
    """
    Распускает команду
    
    Args:
        team: Объект команды
        user: Пользователь, выполняющий действие
        reason: Причина роспуска
    
    Returns:
        bool: True если операция успешна
    
    Raises:
        PermissionError: Если пользователь не имеет прав
        ValueError: Если команда не может быть распущена
    """
    if not team.can_be_managed_by(user):
        logger.warning(f"Пользователь {user.username} попытался распустить команду {team.name} без прав")
        raise PermissionError("Недостаточно прав для управления командой")
    
    if team.status == TeamStatus.DISBANDED:
        logger.warning(f"Попытка распустить уже распущенную команду {team.name}")
        raise ValueError("Команда уже распущена")
    
    old_status = team.status
    team.status = TeamStatus.DISBANDED
    team.save()
    
    # Деактивируем всех участников
    deactivated_count = TeamMembership.objects.filter(team=team).update(is_active=False)
    
    # Записываем в историю
    TeamStatusHistory.objects.create(
        team=team,
        changed_by=user,
        change_type=TeamStatusChangeType.DISBANDED,
        old_status=old_status,
        new_status=team.status,
        reason=reason
    )
    
    logger.info(f"Команда {team.name} распущена пользователем {user.username}. "
                f"Деактивировано участников: {deactivated_count}. Причина: {reason}")
    
    # Отправляем уведомления участникам команды
    try:
        from notifications.services import NotificationService
        NotificationService.send_team_status_notification(
            team=team,
            change_type=TeamStatusChangeType.DISBANDED,
            changed_by=user,
            reason=reason
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений о роспуске команды {team.name}: {e}")
    
    return True


def get_team_status_statistics(user=None):
    """
    Получает статистику по статусам команд
    
    Args:
        user: Пользователь для фильтрации команд (если None, то все команды)
    
    Returns:
        dict: Словарь со статистикой по статусам
    """
    from django.db.models import Q
    
    queryset = Team.objects.all()
    
    if user:
        queryset = queryset.filter(
            Q(members=user) | Q(creator=user)
        ).distinct()
    
    statistics = {
        'active': queryset.filter(status=TeamStatus.ACTIVE).count(),
        'inactive': queryset.filter(status=TeamStatus.INACTIVE).count(),
        'disbanded': queryset.filter(status=TeamStatus.DISBANDED).count(),
        'total': queryset.count()
    }
    
    logger.debug(f"Статистика команд для пользователя {user.username if user else 'всех'}: {statistics}")
    return statistics


def can_perform_team_action(team, user, action):
    """
    Проверяет, может ли пользователь выполнить определенное действие с командой
    
    Args:
        team: Объект команды
        user: Пользователь
        action: Действие ('deactivate', 'reactivate', 'disband')
    
    Returns:
        tuple: (bool, str) - (можно ли выполнить, причина если нельзя)
    """
    if not team.can_be_managed_by(user):
        return False, "Недостаточно прав для управления командой"
    
    if action == 'deactivate':
        if team.status != TeamStatus.ACTIVE:
            return False, "Можно приостановить только активную команду"
    elif action == 'reactivate':
        if team.status != TeamStatus.INACTIVE:
            return False, "Можно возобновить только приостановленную команду"
    elif action == 'disband':
        if team.status == TeamStatus.DISBANDED:
            return False, "Команда уже распущена"
    else:
        return False, "Неизвестное действие"
    
    return True, ""