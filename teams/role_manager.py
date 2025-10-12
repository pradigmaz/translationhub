"""
Менеджер стандартных ролей для системы управления ролями TranslationHub.

Этот модуль содержит класс DefaultRoleManager, который отвечает за создание
и управление стандартными ролями системы с их предустановленными разрешениями.
"""

import logging
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import Role

logger = logging.getLogger(__name__)


class DefaultRoleManager:
    """
    Менеджер для управления стандартными ролями системы.
    
    Отвечает за создание и обновление стандартных ролей с их разрешениями:
    - Руководитель: полные права управления командой и проектами
    - Редактор: управление контентом и рецензирование
    - Переводчик: создание и редактирование переводов
    - Клинер: обработка изображений и очистка
    - Тайпер: типографское оформление
    """
    
    # Определение стандартных ролей с их разрешениями
    DEFAULT_ROLES = {
        'Пользователь': {
            'description': 'Базовая роль для всех зарегистрированных пользователей',
            'permissions': []  # Никаких специальных разрешений, только базовые права Django
        },
        'Руководитель': {
            'description': 'Руководитель команды с полными правами управления',
            'permissions': [
                # Разрешения для команд
                'teams.can_manage_team',
                'teams.can_invite_members',
                'teams.can_remove_members',
                'teams.can_assign_roles',
                'teams.can_change_team_status',
                # Разрешения для проектов
                'teams.can_create_project',
                'teams.can_manage_project',
                'teams.can_delete_project',
                'teams.can_assign_chapters',
                # Разрешения для контента
                'teams.can_edit_content',
                'teams.can_review_content',
                'teams.can_publish_content',
            ]
        },
        'Редактор': {
            'description': 'Редактор с правами проверки и адаптации переводов',
            'permissions': [
                # Разрешения для работы с переводами
                'teams.can_edit_content',
                'teams.can_review_content',
            ]
        },
        'Переводчик': {
            'description': 'Переводчик с правами создания и редактирования переводов',
            'permissions': [
                # Разрешения для контента
                'teams.can_edit_content',
            ]
        },
        'Клинер': {
            'description': 'Клинер с правами обработки изображений и очистки',
            'permissions': [
                # Разрешения для контента
                'teams.can_edit_content',
            ]
        },
        'Тайпер': {
            'description': 'Тайпер с правами типографского оформления',
            'permissions': [
                # Разрешения для контента
                'teams.can_edit_content',
            ]
        }
    }
    
    @classmethod
    def ensure_default_roles_exist(cls, user=None):
        """
        Создает стандартные роли если они не существуют.
        
        Проверяет наличие каждой стандартной роли в системе и создает
        отсутствующие роли с соответствующими разрешениями.
        
        Args:
            user: Пользователь, инициировавший создание ролей (для аудита)
        
        Returns:
            dict: Словарь с результатами создания ролей
                {
                    'created': [список созданных ролей],
                    'updated': [список обновленных ролей],
                    'errors': [список ошибок]
                }
        """
        from .audit_logger import RoleAuditLogger
        
        results = {
            'created': [],
            'updated': [],
            'errors': []
        }
        
        logger.info("Начинаем проверку и создание стандартных ролей")
        
        for role_name, role_data in cls.DEFAULT_ROLES.items():
            try:
                with transaction.atomic():
                    role, created = cls.get_or_create_role(
                        name=role_name,
                        description=role_data['description'],
                        permissions=role_data['permissions'],
                        user=user
                    )
                    
                    if created:
                        results['created'].append(role_name)
                        logger.info(f"Создана стандартная роль: {role_name}")
                    else:
                        # Проверяем и обновляем разрешения для существующей роли
                        updated = cls._update_role_permissions(role, role_data['permissions'])
                        if updated:
                            results['updated'].append(role_name)
                            logger.info(f"Обновлены разрешения для роли: {role_name}")
                        
            except Exception as e:
                error_msg = f"Ошибка при создании роли {role_name}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Логируем результаты создания стандартных ролей
        if results['created'] or results['updated']:
            RoleAuditLogger.log_default_roles_creation(
                user=user,
                created_roles=results['created'],
                updated_roles=results['updated']
            )
        
        logger.info(f"Завершена проверка стандартных ролей. "
                   f"Создано: {len(results['created'])}, "
                   f"Обновлено: {len(results['updated'])}, "
                   f"Ошибок: {len(results['errors'])}")
        
        return results
    
    @classmethod
    def get_or_create_role(cls, name, description, permissions, user=None):
        """
        Создает или получает роль с указанными разрешениями.
        
        Args:
            name (str): Название роли
            description (str): Описание роли
            permissions (list): Список кодовых имен разрешений
            user: Пользователь для аудита (опционально)
            
        Returns:
            tuple: (Role, created) - объект роли и флаг создания
            
        Raises:
            Exception: При ошибке создания роли или назначения разрешений
        """
        try:
            role, created = Role.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'is_default': True
                }
            )
            
            # Устанавливаем пользователя для аудита
            if user:
                role._audit_user = user
            
            if created:
                # Назначаем разрешения новой роли
                cls._assign_permissions_to_role(role, permissions)
            
            return role, created
            
        except Exception as e:
            logger.error(f"Ошибка при создании/получении роли {name}: {str(e)}")
            raise Exception(f"Не удалось создать роль {name}: {str(e)}")
    
    @classmethod
    def _assign_permissions_to_role(cls, role, permission_codenames):
        """
        Назначает разрешения роли.
        
        Args:
            role (Role): Объект роли
            permission_codenames (list): Список кодовых имен разрешений
        """
        permissions_to_add = []
        
        for permission_codename in permission_codenames:
            try:
                # Разбираем полное имя разрешения (app_label.codename)
                if '.' in permission_codename:
                    app_label, codename = permission_codename.split('.', 1)
                else:
                    # Если не указано приложение, предполагаем teams
                    app_label = 'teams'
                    codename = permission_codename
                
                # Ищем разрешение
                permission = Permission.objects.filter(
                    codename=codename,
                    content_type__app_label=app_label
                ).first()
                
                if permission:
                    permissions_to_add.append(permission)
                else:
                    logger.warning(f"Разрешение не найдено: {permission_codename}")
                    
            except Exception as e:
                logger.error(f"Ошибка при поиске разрешения {permission_codename}: {str(e)}")
        
        # Добавляем все найденные разрешения
        if permissions_to_add:
            role.permissions.add(*permissions_to_add)
            logger.debug(f"Добавлено {len(permissions_to_add)} разрешений к роли {role.name}")
    
    @classmethod
    def _update_role_permissions(cls, role, permission_codenames):
        """
        Обновляет разрешения существующей роли.
        
        Args:
            role (Role): Объект роли
            permission_codenames (list): Список кодовых имен разрешений
            
        Returns:
            bool: True если разрешения были обновлены
        """
        current_permissions = set(role.get_permission_names())
        expected_permissions = set()
        
        # Получаем ожидаемые разрешения
        for permission_codename in permission_codenames:
            if '.' in permission_codename:
                _, codename = permission_codename.split('.', 1)
            else:
                codename = permission_codename
            expected_permissions.add(codename)
        
        # Проверяем нужно ли обновление
        if current_permissions == expected_permissions:
            return False
        
        # Очищаем текущие разрешения и назначаем новые
        role.permissions.clear()
        cls._assign_permissions_to_role(role, permission_codenames)
        
        return True
    
    @classmethod
    def recreate_role(cls, role_name):
        """
        Пересоздает стандартную роль с правильными разрешениями.
        
        Args:
            role_name (str): Название роли для пересоздания
            
        Returns:
            Role: Пересозданная роль
            
        Raises:
            ValueError: Если роль не является стандартной
            Exception: При ошибке пересоздания
        """
        if role_name not in cls.DEFAULT_ROLES:
            raise ValueError(f"Роль {role_name} не является стандартной")
        
        try:
            with transaction.atomic():
                # Удаляем существующую роль если она есть
                Role.objects.filter(name=role_name).delete()
                
                # Создаем роль заново
                role_data = cls.DEFAULT_ROLES[role_name]
                role, _ = cls.get_or_create_role(
                    name=role_name,
                    description=role_data['description'],
                    permissions=role_data['permissions']
                )
                
                logger.info(f"Роль {role_name} успешно пересоздана")
                return role
                
        except Exception as e:
            logger.error(f"Ошибка при пересоздании роли {role_name}: {str(e)}")
            raise Exception(f"Не удалось пересоздать роль {role_name}: {str(e)}")
    
    @classmethod
    def get_default_role_names(cls):
        """
        Возвращает список названий стандартных ролей.
        
        Returns:
            list: Список названий стандартных ролей
        """
        return list(cls.DEFAULT_ROLES.keys())
    
    @classmethod
    def is_default_role(cls, role_name):
        """
        Проверяет является ли роль стандартной.
        
        Args:
            role_name (str): Название роли
            
        Returns:
            bool: True если роль стандартная
        """
        return role_name in cls.DEFAULT_ROLES
    
    @classmethod
    def get_role_permissions(cls, role_name):
        """
        Возвращает список разрешений для стандартной роли.
        
        Args:
            role_name (str): Название роли
            
        Returns:
            list: Список разрешений или None если роль не стандартная
        """
        return cls.DEFAULT_ROLES.get(role_name, {}).get('permissions')
    
    @classmethod
    def get_default_user_role(cls):
        """
        Возвращает дефолтную роль для новых пользователей.
        
        Returns:
            Role: Объект роли "Пользователь" или None если не найдена
        """
        try:
            return Role.objects.get(name='Пользователь', is_default=True)
        except Role.DoesNotExist:
            logger.error("Дефолтная роль 'Пользователь' не найдена")
            return None
    
    @classmethod
    def assign_default_role_to_user(cls, user):
        """
        Назначает дефолтную роль новому пользователю.
        
        Создает глобальное членство пользователя с базовой ролью.
        Это позволяет отслеживать всех пользователей системы.
        
        Args:
            user: Объект пользователя Django
            
        Returns:
            bool: True если роль успешно назначена
        """
        try:
            default_role = cls.get_default_user_role()
            if not default_role:
                logger.error(f"Не удалось получить дефолтную роль для пользователя {user.username}")
                return False
            
            # Создаем запись о том, что пользователь имеет базовую роль
            # Это не привязано к конкретной команде, а является глобальным статусом
            from .models import UserRole
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=default_role,
                defaults={'is_active': True}
            )
            
            if created:
                logger.info(f"Назначена дефолтная роль '{default_role.name}' пользователю {user.username}")
            else:
                logger.debug(f"Пользователь {user.username} уже имеет дефолтную роль")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при назначении дефолтной роли пользователю {user.username}: {str(e)}")
            return False