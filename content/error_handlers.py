from django.shortcuts import render
from django.http import JsonResponse
from django.contrib import messages
from django.urls import reverse
from .middleware import ContentActionLogger
from .exceptions import ContentAccessDenied, ProjectAccessDenied, TextContentAccessDenied


def handle_content_permission_denied(request, exception):
    """Обработчик для ошибок доступа к контенту"""
    
    # Логируем попытку несанкционированного доступа
    if hasattr(exception, 'object_type') and hasattr(exception, 'object_id'):
        ContentActionLogger.log_access_denied(
            request.user if request.user.is_authenticated else None,
            'access',
            exception.object_type,
            exception.object_id
        )
    
    # Определяем контекст для шаблона
    context = {
        'error_message': str(exception),
        'error_type': 'access_denied',
        'object_type': getattr(exception, 'object_type', None),
        'suggestions': _get_access_suggestions(exception),
        'back_url': _get_back_url(request, exception)
    }
    
    # Если это AJAX запрос, возвращаем JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'error': True,
            'message': str(exception),
            'error_type': 'access_denied',
            'redirect_url': context['back_url']
        }, status=403)
    
    # Добавляем сообщение об ошибке
    messages.error(request, str(exception))
    
    # Возвращаем шаблон с ошибкой
    return render(request, 'content/errors/403.html', context, status=403)


def _get_access_suggestions(exception):
    """Возвращает предложения по решению проблемы доступа"""
    suggestions = []
    
    if isinstance(exception, ProjectAccessDenied):
        suggestions = [
            "Убедитесь, что вы являетесь участником команды проекта",
            "Проверьте, что команда активна",
            "Обратитесь к руководителю команды для добавления в проект",
            "Свяжитесь с администратором, если считаете, что это ошибка"
        ]
    elif isinstance(exception, TextContentAccessDenied):
        suggestions = [
            "Убедитесь, что у вас есть доступ к проекту этого текста",
            "Проверьте, что вы являетесь участником команды",
            "Возможно, текст был перемещен в другой проект",
            "Обратитесь к автору текста или руководителю команды"
        ]
    else:
        suggestions = [
            "Проверьте, что вы вошли в систему под правильным аккаунтом",
            "Убедитесь, что вы являетесь участником нужной команды",
            "Обратитесь к администратору за помощью"
        ]
    
    return suggestions


def _get_back_url(request, exception):
    """Определяет URL для возврата пользователя"""
    
    # Пытаемся определить подходящий URL для возврата
    if isinstance(exception, (ProjectAccessDenied, TextContentAccessDenied)):
        try:
            return reverse('content:editor')
        except:
            pass
    
    # Если есть HTTP_REFERER, используем его
    referer = request.META.get('HTTP_REFERER')
    if referer and 'content' in referer:
        return referer
    
    # По умолчанию возвращаем на главную страницу редактора
    try:
        return reverse('content:editor')
    except:
        return '/'


class ContentErrorMixin:
    """Миксин для представлений с улучшенной обработкой ошибок доступа"""
    
    def handle_no_permission(self):
        """Переопределяет стандартную обработку отсутствия прав"""
        if hasattr(self, 'get_object'):
            try:
                obj = self.get_object()
                if hasattr(obj, 'project'):
                    raise ProjectAccessDenied(obj.project.id)
                elif obj.__class__.__name__ == 'Project':
                    raise ProjectAccessDenied(obj.id)
            except:
                pass
        
        # Возвращаем стандартную обработку
        return super().handle_no_permission()
    
    def dispatch(self, request, *args, **kwargs):
        """Переопределяет dispatch для лучшей обработки ошибок"""
        try:
            return super().dispatch(request, *args, **kwargs)
        except ContentAccessDenied as e:
            return handle_content_permission_denied(request, e)


def graceful_content_fallback(request, content_type='project'):
    """Предоставляет graceful fallback для недоступного контента"""
    
    context = {
        'content_type': content_type,
        'available_projects': [],
        'recent_texts': [],
        'message': 'Запрашиваемый контент недоступен, но вот что вы можете сделать:'
    }
    
    if request.user.is_authenticated:
        try:
            from .models import Project, TextContent
            
            # Получаем доступные проекты пользователя
            context['available_projects'] = Project.objects.for_user(request.user)[:5]
            
            # Получаем последние тексты пользователя
            context['recent_texts'] = TextContent.objects.recent_for_user(request.user, limit=3)
            
        except Exception:
            pass
    
    return render(request, 'content/errors/content_fallback.html', context)