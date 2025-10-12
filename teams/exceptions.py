"""
Кастомные исключения для приложения teams.

Этот модуль содержит специализированные исключения для обработки
ошибок, связанных с управлением командами и разрешениями.
"""

from django.core.exceptions import PermissionDenied


class TeamPermissionDenied(PermissionDenied):
    """
    Исключение для ошибок разрешений в команде.
    
    Расширяет стандартное PermissionDenied дополнительной информацией
    о команде и требуемом разрешении.
    """
    
    def __init__(self, message=None, team=None, permission=None, user=None):
        """
        Инициализация исключения.
        
        Args:
            message (str): Сообщение об ошибке
            team (Team): Объект команды
            permission (str): Требуемое разрешение
            user (User): Пользователь, которому отказано в доступе
        """
        self.team = team
        self.permission = permission
        self.user = user
        
        if not message:
            if permission and team:
                message = f"У вас нет разрешения '{permission}' в команде '{team.name}'"
            elif team:
                message = f"У вас нет прав для выполнения этого действия в команде '{team.name}'"
            else:
                message = "У вас нет прав для выполнения этого действия в команде"
        
        super().__init__(message)


class TeamNotFoundError(Exception):
    """
    Исключение для случаев, когда команда не найдена.
    """
    
    def __init__(self, team_id=None, message=None):
        """
        Инициализация исключения.
        
        Args:
            team_id (int): ID команды
            message (str): Сообщение об ошибке
        """
        self.team_id = team_id
        
        if not message:
            if team_id:
                message = f"Команда с ID {team_id} не найдена"
            else:
                message = "Команда не найдена"
        
        super().__init__(message)


class TeamStatusError(Exception):
    """
    Исключение для ошибок, связанных со статусом команды.
    """
    
    def __init__(self, team=None, current_status=None, required_status=None, message=None):
        """
        Инициализация исключения.
        
        Args:
            team (Team): Объект команды
            current_status (str): Текущий статус команды
            required_status (str): Требуемый статус команды
            message (str): Сообщение об ошибке
        """
        self.team = team
        self.current_status = current_status
        self.required_status = required_status
        
        if not message:
            if team and current_status and required_status:
                message = (
                    f"Команда '{team.name}' имеет статус '{current_status}', "
                    f"но требуется статус '{required_status}'"
                )
            elif team and current_status:
                message = f"Команда '{team.name}' имеет неподходящий статус '{current_status}'"
            else:
                message = "Неподходящий статус команды для выполнения операции"
        
        super().__init__(message)


class RoleAssignmentError(Exception):
    """
    Исключение для ошибок назначения ролей.
    """
    
    def __init__(self, user=None, role=None, team=None, message=None):
        """
        Инициализация исключения.
        
        Args:
            user (User): Пользователь
            role (Role): Роль
            team (Team): Команда
            message (str): Сообщение об ошибке
        """
        self.user = user
        self.role = role
        self.team = team
        
        if not message:
            if user and role and team:
                message = f"Не удалось назначить роль '{role.name}' пользователю '{user.username}' в команде '{team.name}'"
            else:
                message = "Ошибка при назначении роли"
        
        super().__init__(message)