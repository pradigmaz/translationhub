"""
Сигналы для автоматического управления ролями пользователей.

Этот модуль содержит сигналы Django для:
- Автоматического назначения дефолтной роли новым пользователям
- Логирования изменений ролей
- Обновления статуса пользователей при изменении ролей
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def assign_default_role_to_new_user(sender, instance, created, **kwargs):
    """
    Автоматически назначает дефолтную роль новому пользователю при регистрации.
    
    Этот сигнал срабатывает при создании нового пользователя и:
    1. Получает дефолтную роль "Пользователь"
    2. Создает запись UserRole для нового пользователя
    3. Логирует результат операции
    
    Args:
        sender: Модель User
        instance: Экземпляр созданного пользователя
        created (bool): True если пользователь был создан (не обновлен)
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:  # Только для новых пользователей
        try:
            from .models import UserRole
            from .role_manager import DefaultRoleManager
            
            # Получаем дефолтную роль
            default_role = DefaultRoleManager.get_default_user_role()
            
            if default_role:
                # Создаем глобальную роль для пользователя
                user_role, role_created = UserRole.objects.get_or_create(
                    user=instance,
                    role=default_role,
                    defaults={
                        'is_active': True,
                        'assigned_by': None  # Автоматическое назначение системой
                    }
                )
                
                if role_created:
                    logger.info(f"Автоматически назначена дефолтная роль '{default_role.name}' "
                               f"пользователю {instance.username} (ID: {instance.id})")
                else:
                    logger.debug(f"Пользователь {instance.username} уже имеет дефолтную роль")
            else:
                logger.error(f"Не удалось получить дефолтную роль для нового пользователя {instance.username}")
                
        except Exception as e:
            logger.error(f"Ошибка при назначении дефолтной роли пользователю {instance.username}: {str(e)}")


@receiver(post_save, sender='teams.UserRole')
def log_user_role_changes(sender, instance, created, **kwargs):
    """
    Логирует изменения в глобальных ролях пользователей.
    
    Args:
        sender: Модель UserRole
        instance: Экземпляр UserRole
        created (bool): True если роль была создана
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:
        logger.info(f"Создана глобальная роль: {instance.user.username} -> {instance.role.name}")
    else:
        status = "активна" if instance.is_active else "деактивирована"
        logger.info(f"Обновлена глобальная роль: {instance.user.username} -> {instance.role.name} ({status})")


@receiver(post_save, sender='teams.Team')
def assign_leader_role_to_team_creator(sender, instance, created, **kwargs):
    """
    Автоматически назначает роль "Руководитель" создателю команды.
    
    Этот сигнал срабатывает при создании новой команды и:
    1. Создает TeamMembership для создателя команды
    2. Назначает роль "Руководитель" создателю
    3. Логирует результат операции
    
    Args:
        sender: Модель Team
        instance: Экземпляр созданной команды
        created (bool): True если команда была создана (не обновлена)
        **kwargs: Дополнительные аргументы сигнала
    """
    if created and instance.creator:  # Только для новых команд с создателем
        try:
            from .models import TeamMembership
            from .role_manager import DefaultRoleManager
            
            # Получаем роль "Руководитель"
            leader_role = None
            try:
                from .models import Role
                leader_role = Role.objects.get(name='Руководитель', is_default=True)
            except Role.DoesNotExist:
                # Если роль не найдена, создаем её через DefaultRoleManager
                DefaultRoleManager.ensure_default_roles_exist()
                leader_role = Role.objects.get(name='Руководитель', is_default=True)
            
            if leader_role:
                # Создаем членство в команде для создателя
                membership, membership_created = TeamMembership.objects.get_or_create(
                    user=instance.creator,
                    team=instance,
                    defaults={'is_active': True}
                )
                
                # Назначаем роль "Руководитель"
                membership.roles.add(leader_role)
                
                logger.info(f"Автоматически назначена роль 'Руководитель' создателю команды "
                           f"{instance.creator.username} в команде '{instance.name}' (ID: {instance.id})")
                
                # Обновляем глобальный статус пользователя если он был новичком
                if hasattr(instance.creator, 'is_default_user') and instance.creator.is_default_user():
                    logger.info(f"Пользователь {instance.creator.username} больше не является новичком - "
                               f"стал руководителем команды '{instance.name}'")
            else:
                logger.error(f"Не удалось получить роль 'Руководитель' для назначения создателю команды {instance.name}")
                
        except Exception as e:
            logger.error(f"Ошибка при назначении роли руководителя создателю команды {instance.name}: {str(e)}")