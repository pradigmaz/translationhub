# teams/audit_logger.py

import logging
from datetime import datetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from typing import Optional, List, Dict, Any

User = get_user_model()

# Создаем специальный логгер для аудита ролей
role_audit_logger = logging.getLogger('teams.role_audit')


class RoleAuditLogger:
    """
    Класс для логирования операций с ролями и разрешениями.
    
    Обеспечивает централизованное логирование всех операций связанных с:
    - Созданием, изменением и удалением ролей
    - Назначением и удалением разрешений у ролей
    - Назначением и удалением ролей у пользователей
    - Изменениями в административном интерфейсе
    """
    
    @staticmethod
    def _format_user_info(user: Optional[User]) -> str:
        """Форматирует информацию о пользователе для логов"""
        if not user:
            return "Система"
        if user.is_superuser:
            return f"{user.username} (суперпользователь)"
        return f"{user.username} (ID: {user.id})"
    
    @staticmethod
    def _format_permissions(permissions: List[str]) -> str:
        """Форматирует список разрешений для логов"""
        if not permissions:
            return "нет разрешений"
        return ", ".join(permissions)
    
    @staticmethod
    def log_role_created(user: Optional[User], role_name: str, description: str = "", 
                        permissions: List[str] = None, is_default: bool = False) -> None:
        """
        Логирует создание новой роли
        
        Args:
            user: Пользователь, создавший роль
            role_name: Название роли
            description: Описание роли
            permissions: Список разрешений роли
            is_default: Является ли роль стандартной
        """
        permissions = permissions or []
        user_info = RoleAuditLogger._format_user_info(user)
        permissions_info = RoleAuditLogger._format_permissions(permissions)
        
        role_audit_logger.info(
            f"СОЗДАНИЕ_РОЛИ | Пользователь: {user_info} | "
            f"Роль: '{role_name}' | Описание: '{description}' | "
            f"Стандартная: {is_default} | Разрешения: [{permissions_info}] | "
            f"Количество разрешений: {len(permissions)}"
        )
    
    @staticmethod
    def log_role_updated(user: Optional[User], role_name: str, 
                        changes: Dict[str, Any]) -> None:
        """
        Логирует изменение роли
        
        Args:
            user: Пользователь, изменивший роль
            role_name: Название роли
            changes: Словарь изменений (поле -> (старое_значение, новое_значение))
        """
        user_info = RoleAuditLogger._format_user_info(user)
        
        changes_info = []
        for field, (old_value, new_value) in changes.items():
            if field == 'permissions':
                old_perms = RoleAuditLogger._format_permissions(old_value or [])
                new_perms = RoleAuditLogger._format_permissions(new_value or [])
                changes_info.append(f"{field}: [{old_perms}] → [{new_perms}]")
            else:
                changes_info.append(f"{field}: '{old_value}' → '{new_value}'")
        
        changes_str = " | ".join(changes_info)
        
        role_audit_logger.info(
            f"ИЗМЕНЕНИЕ_РОЛИ | Пользователь: {user_info} | "
            f"Роль: '{role_name}' | Изменения: {changes_str}"
        )
    
    @staticmethod
    def log_role_deleted(user: Optional[User], role_name: str, 
                        usage_count: int = 0, permissions: List[str] = None) -> None:
        """
        Логирует удаление роли
        
        Args:
            user: Пользователь, удаливший роль
            role_name: Название роли
            usage_count: Количество участников, у которых была эта роль
            permissions: Список разрешений удаленной роли
        """
        permissions = permissions or []
        user_info = RoleAuditLogger._format_user_info(user)
        permissions_info = RoleAuditLogger._format_permissions(permissions)
        
        role_audit_logger.warning(
            f"УДАЛЕНИЕ_РОЛИ | Пользователь: {user_info} | "
            f"Роль: '{role_name}' | Использований: {usage_count} | "
            f"Разрешения: [{permissions_info}]"
        )
    
    @staticmethod
    def log_permission_assigned(user: Optional[User], role_name: str, 
                               permission: str) -> None:
        """
        Логирует назначение разрешения роли
        
        Args:
            user: Пользователь, назначивший разрешение
            role_name: Название роли
            permission: Код разрешения
        """
        user_info = RoleAuditLogger._format_user_info(user)
        
        role_audit_logger.info(
            f"НАЗНАЧЕНИЕ_РАЗРЕШЕНИЯ | Пользователь: {user_info} | "
            f"Роль: '{role_name}' | Разрешение: '{permission}'"
        )
    
    @staticmethod
    def log_permission_removed(user: Optional[User], role_name: str, 
                              permission: str) -> None:
        """
        Логирует удаление разрешения у роли
        
        Args:
            user: Пользователь, удаливший разрешение
            role_name: Название роли
            permission: Код разрешения
        """
        user_info = RoleAuditLogger._format_user_info(user)
        
        role_audit_logger.info(
            f"УДАЛЕНИЕ_РАЗРЕШЕНИЯ | Пользователь: {user_info} | "
            f"Роль: '{role_name}' | Разрешение: '{permission}'"
        )
    
    @staticmethod
    def log_role_assigned_to_user(admin_user: Optional[User], target_user: User, 
                                 role_name: str, team_name: str) -> None:
        """
        Логирует назначение роли пользователю в команде
        
        Args:
            admin_user: Администратор, назначивший роль
            target_user: Пользователь, которому назначена роль
            role_name: Название роли
            team_name: Название команды
        """
        admin_info = RoleAuditLogger._format_user_info(admin_user)
        target_info = RoleAuditLogger._format_user_info(target_user)
        
        role_audit_logger.info(
            f"НАЗНАЧЕНИЕ_РОЛИ_ПОЛЬЗОВАТЕЛЮ | Администратор: {admin_info} | "
            f"Пользователь: {target_info} | Роль: '{role_name}' | "
            f"Команда: '{team_name}'"
        )
    
    @staticmethod
    def log_role_removed_from_user(admin_user: Optional[User], target_user: User, 
                                  role_name: str, team_name: str) -> None:
        """
        Логирует удаление роли у пользователя в команде
        
        Args:
            admin_user: Администратор, удаливший роль
            target_user: Пользователь, у которого удалена роль
            role_name: Название роли
            team_name: Название команды
        """
        admin_info = RoleAuditLogger._format_user_info(admin_user)
        target_info = RoleAuditLogger._format_user_info(target_user)
        
        role_audit_logger.info(
            f"УДАЛЕНИЕ_РОЛИ_У_ПОЛЬЗОВАТЕЛЯ | Администратор: {admin_info} | "
            f"Пользователь: {target_info} | Роль: '{role_name}' | "
            f"Команда: '{team_name}'"
        )
    
    @staticmethod
    def log_bulk_role_assignment(admin_user: Optional[User], role_name: str, 
                                user_count: int, team_name: str = None) -> None:
        """
        Логирует массовое назначение ролей
        
        Args:
            admin_user: Администратор, выполнивший массовое назначение
            role_name: Название роли
            user_count: Количество пользователей
            team_name: Название команды (если применимо)
        """
        admin_info = RoleAuditLogger._format_user_info(admin_user)
        team_info = f" | Команда: '{team_name}'" if team_name else ""
        
        role_audit_logger.info(
            f"МАССОВОЕ_НАЗНАЧЕНИЕ_РОЛЕЙ | Администратор: {admin_info} | "
            f"Роль: '{role_name}' | Количество пользователей: {user_count}{team_info}"
        )
    
    @staticmethod
    def log_bulk_role_removal(admin_user: Optional[User], role_name: str = None, 
                             user_count: int = 0, team_name: str = None) -> None:
        """
        Логирует массовое удаление ролей
        
        Args:
            admin_user: Администратор, выполнивший массовое удаление
            role_name: Название роли (если удаляется конкретная роль)
            user_count: Количество пользователей
            team_name: Название команды (если применимо)
        """
        admin_info = RoleAuditLogger._format_user_info(admin_user)
        role_info = f"Роль: '{role_name}'" if role_name else "Все роли"
        team_info = f" | Команда: '{team_name}'" if team_name else ""
        
        role_audit_logger.info(
            f"МАССОВОЕ_УДАЛЕНИЕ_РОЛЕЙ | Администратор: {admin_info} | "
            f"{role_info} | Количество пользователей: {user_count}{team_info}"
        )
    
    @staticmethod
    def log_default_roles_creation(user: Optional[User], created_roles: List[str], 
                                  updated_roles: List[str] = None) -> None:
        """
        Логирует создание стандартных ролей
        
        Args:
            user: Пользователь, инициировавший создание (может быть None для системных операций)
            created_roles: Список созданных ролей
            updated_roles: Список обновленных ролей
        """
        user_info = RoleAuditLogger._format_user_info(user)
        updated_roles = updated_roles or []
        
        role_audit_logger.info(
            f"СОЗДАНИЕ_СТАНДАРТНЫХ_РОЛЕЙ | Инициатор: {user_info} | "
            f"Создано ролей: {len(created_roles)} [{', '.join(created_roles)}] | "
            f"Обновлено ролей: {len(updated_roles)} [{', '.join(updated_roles)}]"
        )
    
    @staticmethod
    def log_admin_action(admin_user: Optional[User], action: str, 
                        target_object: str, details: str = "") -> None:
        """
        Логирует действия в административном интерфейсе
        
        Args:
            admin_user: Администратор, выполнивший действие
            action: Тип действия (CREATE, UPDATE, DELETE, etc.)
            target_object: Объект, над которым выполнено действие
            details: Дополнительные детали
        """
        admin_info = RoleAuditLogger._format_user_info(admin_user)
        details_info = f" | Детали: {details}" if details else ""
        
        role_audit_logger.info(
            f"АДМИН_ДЕЙСТВИЕ | Администратор: {admin_info} | "
            f"Действие: {action} | Объект: {target_object}{details_info}"
        )
    
    @staticmethod
    def log_permission_check_failure(user: User, permission: str, 
                                   team_name: str, context: str = "") -> None:
        """
        Логирует неудачные попытки доступа (для безопасности)
        
        Args:
            user: Пользователь, попытавшийся получить доступ
            permission: Требуемое разрешение
            team_name: Название команды
            context: Контекст попытки доступа
        """
        user_info = RoleAuditLogger._format_user_info(user)
        context_info = f" | Контекст: {context}" if context else ""
        
        role_audit_logger.warning(
            f"ОТКАЗ_В_ДОСТУПЕ | Пользователь: {user_info} | "
            f"Разрешение: '{permission}' | Команда: '{team_name}'{context_info}"
        )
    
    @staticmethod
    def log_system_event(event_type: str, details: str, 
                        severity: str = "INFO") -> None:
        """
        Логирует системные события связанные с ролями
        
        Args:
            event_type: Тип события
            details: Детали события
            severity: Уровень важности (INFO, WARNING, ERROR)
        """
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_method = getattr(role_audit_logger, severity.lower(), role_audit_logger.info)
        log_method(
            f"СИСТЕМНОЕ_СОБЫТИЕ | Время: {timestamp} | "
            f"Тип: {event_type} | Детали: {details}"
        )