"""
Миксины для расширения функциональности пользователя в системе ролей.

Этот модуль содержит миксины, которые можно использовать для расширения
модели User дополнительными методами работы с ролями.
"""

from django.db import models


class UserRoleMixin:
    """
    Миксин для добавления методов работы с глобальными ролями пользователя.
    
    Предоставляет удобные методы для:
    - Получения активных глобальных ролей пользователя
    - Проверки наличия конкретной роли
    - Получения всех разрешений пользователя
    - Проверки является ли пользователь новичком (имеет только дефолтную роль)
    """
    
    def get_global_roles(self, active_only=True):
        """
        Возвращает глобальные роли пользователя.
        
        Args:
            active_only (bool): Возвращать только активные роли
            
        Returns:
            QuerySet: Набор объектов Role
        """
        from .models import UserRole
        
        user_roles = UserRole.objects.filter(user=self)
        if active_only:
            user_roles = user_roles.filter(is_active=True)
        
        return user_roles.select_related('role')
    
    def has_global_role(self, role_name):
        """
        Проверяет имеет ли пользователь конкретную глобальную роль.
        
        Args:
            role_name (str): Название роли
            
        Returns:
            bool: True если пользователь имеет роль
        """
        return self.get_global_roles().filter(role__name=role_name).exists()
    
    def is_default_user(self):
        """
        Проверяет является ли пользователь новичком (имеет только дефолтную роль).
        
        Returns:
            bool: True если у пользователя только роль "Пользователь"
        """
        global_roles = self.get_global_roles()
        return (global_roles.count() == 1 and 
                global_roles.filter(role__name='Пользователь').exists())
    
    def get_all_permissions_from_roles(self):
        """
        Возвращает все разрешения пользователя из его глобальных ролей.
        
        Returns:
            QuerySet: Набор объектов Permission
        """
        from django.contrib.auth.models import Permission
        
        role_ids = self.get_global_roles().values_list('role_id', flat=True)
        return Permission.objects.filter(roles__id__in=role_ids).distinct()
    
    def add_global_role(self, role_name, assigned_by=None):
        """
        Добавляет глобальную роль пользователю.
        
        Args:
            role_name (str): Название роли
            assigned_by: Пользователь, который назначает роль
            
        Returns:
            tuple: (UserRole, created) - объект роли и флаг создания
        """
        from .models import Role, UserRole
        
        try:
            role = Role.objects.get(name=role_name)
            user_role, created = UserRole.objects.get_or_create(
                user=self,
                role=role,
                defaults={
                    'is_active': True,
                    'assigned_by': assigned_by
                }
            )
            
            if not created and not user_role.is_active:
                # Реактивируем роль если она была деактивирована
                user_role.reactivate(assigned_by)
            
            return user_role, created
            
        except Role.DoesNotExist:
            raise ValueError(f"Роль '{role_name}' не найдена")
    
    def remove_global_role(self, role_name, removed_by=None):
        """
        Удаляет (деактивирует) глобальную роль пользователя.
        
        Args:
            role_name (str): Название роли
            removed_by: Пользователь, который удаляет роль
            
        Returns:
            bool: True если роль была деактивирована
        """
        from .models import UserRole
        
        try:
            user_role = UserRole.objects.get(
                user=self,
                role__name=role_name,
                is_active=True
            )
            user_role.deactivate(removed_by)
            return True
            
        except UserRole.DoesNotExist:
            return False
    
    def get_role_summary(self):
        """
        Возвращает краткую сводку о ролях пользователя.
        
        Returns:
            dict: Словарь с информацией о ролях
        """
        global_roles = self.get_global_roles()
        team_memberships = getattr(self, 'teammembership_set', None)
        
        summary = {
            'global_roles': [ur.role.name for ur in global_roles],
            'global_roles_count': global_roles.count(),
            'is_default_user': self.is_default_user(),
            'team_memberships': []
        }
        
        if team_memberships:
            for membership in team_memberships.filter(is_active=True).select_related('team'):
                team_roles = [role.name for role in membership.roles.all()]
                summary['team_memberships'].append({
                    'team': membership.team.name,
                    'roles': team_roles
                })
        
        return summary


def add_role_methods_to_user():
    """
    Добавляет методы работы с ролями к модели User.
    
    Эта функция должна быть вызвана в apps.py для расширения
    стандартной модели User методами из UserRoleMixin.
    """
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Добавляем методы из миксина к модели User
    for method_name in dir(UserRoleMixin):
        if not method_name.startswith('_'):
            method = getattr(UserRoleMixin, method_name)
            if callable(method):
                setattr(User, method_name, method)