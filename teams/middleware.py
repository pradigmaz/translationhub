"""
Middleware для обработки ошибок разрешений в приложении teams.

Этот middleware перехватывает исключения PermissionDenied в представлениях команд
и отображает пользовательские страницы ошибок с понятными сообщениями.
"""

import logging
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.urls import resolve

logger = logging.getLogger(__name__)


class TeamPermissionMiddleware:
    """
    Middleware для обработки ошибок разрешений в команде.
    
    Перехватывает исключения PermissionDenied в представлениях команд
    и отображает кастомную страницу ошибки с подробной информацией.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Обрабатывает исключения PermissionDenied для представлений команд.
        
        Args:
            request: HTTP запрос
            exception: Исключение
            
        Returns:
            HttpResponse: Кастомная страница ошибки или None
        """
        if not isinstance(exception, PermissionDenied):
            return None
        
        # Проверяем, что это запрос к представлению команды
        try:
            resolved = resolve(request.path)
            if not resolved.app_name == 'teams':
                return None
        except:
            return None
        
        # Логируем ошибку доступа
        logger.warning(
            f"Ошибка доступа к команде для пользователя {request.user.username if request.user.is_authenticated else 'Anonymous'}: "
            f"{str(exception)} на URL {request.path}"
        )
        
        # Определяем контекст для страницы ошибки
        error_message = str(exception) if str(exception) else "У вас нет прав для выполнения этого действия в команде"
        
        suggestions = [
            "Убедитесь, что вы являетесь участником команды",
            "Проверьте, что ваша роль в команде имеет необходимые разрешения",
            "Обратитесь к руководителю команды для назначения соответствующих прав",
            "Свяжитесь с администратором системы, если считаете, что произошла ошибка"
        ]
        
        # Определяем тип действия по URL
        action_type = self._get_action_type_from_url(request.path)
        if action_type:
            suggestions.insert(0, f"Для выполнения действия '{action_type}' требуются дополнительные разрешения")
        
        context = {
            'error_message': error_message,
            'object_type': 'Команда',
            'error_type': 'permission_denied',
            'suggestions': suggestions,
            'back_url': request.META.get('HTTP_REFERER'),
            'action_type': action_type,
        }
        
        return render(request, 'teams/errors/403.html', context, status=403)
    
    def _get_action_type_from_url(self, path):
        """
        Определяет тип действия по URL для более точного сообщения об ошибке.
        
        Args:
            path (str): URL путь
            
        Returns:
            str: Описание действия или None
        """
        if '/status/' in path:
            return 'изменение статуса команды'
        elif '/create/' in path:
            return 'создание команды'
        elif '/history/' in path:
            return 'просмотр истории команды'
        elif path.endswith('/'):
            return 'просмотр информации о команде'
        else:
            return None