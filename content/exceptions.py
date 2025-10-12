from django.core.exceptions import PermissionDenied
from django.http import Http404


class ContentAccessDenied(PermissionDenied):
    """Исключение для отказа в доступе к контенту"""
    
    def __init__(self, message="У вас нет доступа к этому контенту", object_type=None, object_id=None):
        self.object_type = object_type
        self.object_id = object_id
        super().__init__(message)


class ProjectAccessDenied(ContentAccessDenied):
    """Исключение для отказа в доступе к проекту"""
    
    def __init__(self, project_id=None, message=None):
        if not message:
            message = "У вас нет доступа к этому проекту. Возможно, вы не являетесь участником команды или команда неактивна."
        super().__init__(message, 'Project', project_id)


class TextContentAccessDenied(ContentAccessDenied):
    """Исключение для отказа в доступе к текстовому контенту"""
    
    def __init__(self, text_id=None, message=None):
        if not message:
            message = "У вас нет доступа к этому тексту. Возможно, вы не являетесь участником команды проекта."
        super().__init__(message, 'TextContent', text_id)


class ImageContentAccessDenied(ContentAccessDenied):
    """Исключение для отказа в доступе к изображению"""
    
    def __init__(self, image_id=None, message=None):
        if not message:
            message = "У вас нет доступа к этому изображению. Возможно, вы не являетесь участником команды проекта."
        super().__init__(message, 'ImageContent', image_id)


class InactiveTeamError(ContentAccessDenied):
    """Исключение для попытки доступа к контенту неактивной команды"""
    
    def __init__(self, team_name=None):
        message = f"Команда '{team_name}' неактивна. Обратитесь к администратору." if team_name else "Команда неактивна."
        super().__init__(message, 'Team')


class ContentNotFoundError(Http404):
    """Исключение для случаев, когда контент не найден или недоступен"""
    
    def __init__(self, message="Запрашиваемый контент не найден или недоступен"):
        super().__init__(message)