"""
Система проверки разрешений для управления ролями TranslationHub.

Этот модуль содержит класс RolePermissionChecker, который отвечает за проверку
разрешений пользователей в командах на основе их назначенных ролей.
"""

import logging
from django.db.models import Q

logger = logging.getLogger(__name__)


class RolePermissionChecker:
    """
    Класс для проверки разрешений пользователей в командах.
    
    Предоставляет методы для проверки разрешений пользователей на основе
    их ролей в конкретных командах, а также для получения всех разрешений
    пользователя в команде.
    """
    
    @staticmethod
    def user_has_team_permission(user, team, permission):
        """
        Проверяет есть ли у пользователя конкретное разрешение в команде.
        
        Args:
            user: Объект пользователя Django
            team: Объект команды (Team)
            permission (str): Кодовое имя разрешения (например, 'can_manage_team')
            
        Returns:
            bool: True если у пользователя есть разрешение в команде
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> has_permission = checker.user_has_team_permission(
            ...     user, team, 'can_manage_team'
            ... )
        """
        if not user or not user.is_authenticated:
            logger.debug("Пользователь не аутентифицирован")
            return False
        
        if not team:
            logger.debug("Команда не указана")
            return False
        
        # Суперпользователи имеют все разрешения
        if user.is_superuser:
            logger.debug(f"Суперпользователь {user.username} имеет все разрешения")
            return True
        
        # Создатель команды имеет все разрешения в своей команде
        if team.creator == user:
            logger.debug(f"Пользователь {user.username} является создателем команды {team.name}")
            return True
        
        try:
            from .models import TeamMembership
            
            # Получаем членство пользователя в команде
            membership = TeamMembership.objects.filter(
                user=user,
                team=team,
                is_active=True
            ).prefetch_related('roles__permissions').first()
            
            if not membership:
                logger.debug(f"Пользователь {user.username} не является активным участником команды {team.name}")
                return False
            
            # Проверяем разрешения во всех ролях пользователя
            for role in membership.roles.all():
                if role.has_permission(permission):
                    logger.debug(f"Пользователь {user.username} имеет разрешение {permission} через роль {role.name}")
                    return True
            
            logger.debug(f"Пользователь {user.username} не имеет разрешения {permission} в команде {team.name}")
            
            # Логируем неудачную попытку доступа для аудита безопасности
            from .audit_logger import RoleAuditLogger
            RoleAuditLogger.log_permission_check_failure(
                user=user,
                permission=permission,
                team_name=team.name,
                context="RolePermissionChecker.has_permission"
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке разрешения {permission} для пользователя {user.username} в команде {team.name}: {str(e)}")
            return False
    
    @staticmethod
    def get_user_permissions_in_team(user, team):
        """
        Получает все разрешения пользователя в конкретной команде.
        
        Args:
            user: Объект пользователя Django
            team: Объект команды (Team)
            
        Returns:
            set: Множество кодовых имен разрешений пользователя в команде
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> permissions = checker.get_user_permissions_in_team(user, team)
            >>> print(permissions)
            {'can_edit_content', 'can_manage_project', 'can_invite_members'}
        """
        if not user or not user.is_authenticated:
            logger.debug("Пользователь не аутентифицирован")
            return set()
        
        if not team:
            logger.debug("Команда не указана")
            return set()
        
        # Суперпользователи имеют все разрешения
        if user.is_superuser:
            logger.debug(f"Суперпользователь {user.username} имеет все разрешения")
            return RolePermissionChecker._get_all_team_permissions()
        
        # Создатель команды имеет все разрешения в своей команде
        if team.creator == user:
            logger.debug(f"Пользователь {user.username} является создателем команды {team.name}")
            return RolePermissionChecker._get_all_team_permissions()
        
        try:
            from .models import TeamMembership
            
            # Получаем членство пользователя в команде
            membership = TeamMembership.objects.filter(
                user=user,
                team=team,
                is_active=True
            ).prefetch_related('roles__permissions').first()
            
            if not membership:
                logger.debug(f"Пользователь {user.username} не является активным участником команды {team.name}")
                return set()
            
            # Собираем все разрешения из всех ролей пользователя
            permissions = set()
            for role in membership.roles.all():
                role_permissions = role.get_permission_names()
                permissions.update(role_permissions)
                logger.debug(f"Добавлены разрешения из роли {role.name}: {role_permissions}")
            
            logger.debug(f"Пользователь {user.username} имеет разрешения в команде {team.name}: {permissions}")
            return permissions
            
        except Exception as e:
            logger.error(f"Ошибка при получении разрешений для пользователя {user.username} в команде {team.name}: {str(e)}")
            return set()
    
    @staticmethod
    def filter_teams_by_permission(user, permission):
        """
        Фильтрует команды где у пользователя есть конкретное разрешение.
        
        Args:
            user: Объект пользователя Django
            permission (str): Кодовое имя разрешения
            
        Returns:
            QuerySet: Команды где у пользователя есть указанное разрешение
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> teams = checker.filter_teams_by_permission(user, 'can_manage_team')
        """
        if not user or not user.is_authenticated:
            logger.debug("Пользователь не аутентифицирован")
            return Team.objects.none()
        
        # Суперпользователи имеют доступ ко всем командам
        if user.is_superuser:
            logger.debug(f"Суперпользователь {user.username} имеет доступ ко всем командам")
            return Team.objects.all()
        
        try:
            from .models import Team
            
            # Команды где пользователь является создателем
            creator_teams = Team.objects.filter(creator=user)
            
            # Команды где пользователь имеет разрешение через роли
            permission_teams = Team.objects.filter(
                teammembership__user=user,
                teammembership__is_active=True,
                teammembership__roles__permissions__codename=permission
            ).distinct()
            
            # Объединяем результаты
            teams = creator_teams.union(permission_teams)
            
            logger.debug(f"Пользователь {user.username} имеет разрешение {permission} в {teams.count()} командах")
            return teams
            
        except Exception as e:
            logger.error(f"Ошибка при фильтрации команд по разрешению {permission} для пользователя {user.username}: {str(e)}")
            from .models import Team
            return Team.objects.none()
    
    @staticmethod
    def user_has_any_team_permission(user, team, permissions):
        """
        Проверяет есть ли у пользователя любое из указанных разрешений в команде.
        
        Args:
            user: Объект пользователя Django
            team: Объект команды (Team)
            permissions (list): Список кодовых имен разрешений
            
        Returns:
            bool: True если у пользователя есть хотя бы одно из разрешений
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> has_any = checker.user_has_any_team_permission(
            ...     user, team, ['can_edit_content', 'can_review_content']
            ... )
        """
        if not permissions:
            return False
        
        for permission in permissions:
            if RolePermissionChecker.user_has_team_permission(user, team, permission):
                return True
        
        return False
    
    @staticmethod
    def user_has_all_team_permissions(user, team, permissions):
        """
        Проверяет есть ли у пользователя все указанные разрешения в команде.
        
        Args:
            user: Объект пользователя Django
            team: Объект команды (Team)
            permissions (list): Список кодовых имен разрешений
            
        Returns:
            bool: True если у пользователя есть все указанные разрешения
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> has_all = checker.user_has_all_team_permissions(
            ...     user, team, ['can_edit_content', 'can_review_content']
            ... )
        """
        if not permissions:
            return True
        
        for permission in permissions:
            if not RolePermissionChecker.user_has_team_permission(user, team, permission):
                return False
        
        return True
    
    @staticmethod
    def get_user_teams_with_permission(user, permission):
        """
        Получает список команд где у пользователя есть конкретное разрешение.
        
        Args:
            user: Объект пользователя Django
            permission (str): Кодовое имя разрешения
            
        Returns:
            list: Список объектов команд
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> teams = checker.get_user_teams_with_permission(user, 'can_manage_team')
        """
        teams_queryset = RolePermissionChecker.filter_teams_by_permission(user, permission)
        return list(teams_queryset)
    
    @staticmethod
    def get_team_members_with_permission(team, permission):
        """
        Получает список участников команды с конкретным разрешением.
        
        Args:
            team: Объект команды (Team)
            permission (str): Кодовое имя разрешения
            
        Returns:
            list: Список объектов пользователей
            
        Examples:
            >>> checker = RolePermissionChecker()
            >>> members = checker.get_team_members_with_permission(team, 'can_edit_content')
        """
        if not team:
            return []
        
        try:
            from .models import TeamMembership
            
            # Получаем всех активных участников команды
            memberships = TeamMembership.objects.filter(
                team=team,
                is_active=True
            ).select_related('user').prefetch_related('roles__permissions')
            
            members_with_permission = []
            
            for membership in memberships:
                user = membership.user
                
                # Проверяем разрешение для каждого участника
                if RolePermissionChecker.user_has_team_permission(user, team, permission):
                    members_with_permission.append(user)
            
            logger.debug(f"В команде {team.name} найдено {len(members_with_permission)} участников с разрешением {permission}")
            return members_with_permission
            
        except Exception as e:
            logger.error(f"Ошибка при получении участников команды {team.name} с разрешением {permission}: {str(e)}")
            return []
    
    @staticmethod
    def _get_all_team_permissions():
        """
        Получает все доступные разрешения для команд.
        
        Returns:
            set: Множество всех кодовых имен разрешений для команд
        """
        try:
            # Получаем все разрешения из мета-класса Role
            from .models import Role
            meta_permissions = [perm[0] for perm in Role._meta.permissions]
            return set(meta_permissions)
            
        except Exception as e:
            logger.error(f"Ошибка при получении всех разрешений команд: {str(e)}")
            return set()
    
    @staticmethod
    def check_permission_exists(permission):
        """
        Проверяет существует ли разрешение в системе.
        
        Args:
            permission (str): Кодовое имя разрешения
            
        Returns:
            bool: True если разрешение существует
        """
        try:
            from django.contrib.auth.models import Permission
            
            return Permission.objects.filter(
                codename=permission,
                content_type__app_label='teams'
            ).exists()
            
        except Exception as e:
            logger.error(f"Ошибка при проверке существования разрешения {permission}: {str(e)}")
            return False