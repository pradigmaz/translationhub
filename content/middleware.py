import logging
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger('content.audit')


class ContentAuditMiddleware(MiddlewareMixin):
    """Middleware для аудита действий с контентом"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Обрабатывает представления для логирования действий"""
        
        # Пропускаем анонимных пользователей
        if isinstance(request.user, AnonymousUser):
            return None
        
        # Определяем тип действия по URL и методу
        action_info = self._get_action_info(request, view_func, view_kwargs)
        
        if action_info:
            # Сохраняем информацию о действии в request для использования в process_response
            request._audit_info = {
                'user': request.user,
                'action': action_info['action'],
                'object_type': action_info.get('object_type'),
                'object_id': action_info.get('object_id'),
                'ip_address': self._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
            }
        
        return None
    
    def process_response(self, request, response):
        """Логирует действие после обработки запроса"""
        
        if hasattr(request, '_audit_info') and response.status_code < 400:
            audit_info = request._audit_info
            
            # Формируем сообщение для лога
            message = (
                f"User {audit_info['user'].username} performed {audit_info['action']}"
            )
            
            if audit_info.get('object_type') and audit_info.get('object_id'):
                message += f" on {audit_info['object_type']} ID {audit_info['object_id']}"
            
            message += f" from IP {audit_info['ip_address']}"
            
            # Логируем действие
            logger.info(message, extra={
                'user_id': audit_info['user'].id,
                'username': audit_info['user'].username,
                'action': audit_info['action'],
                'object_type': audit_info.get('object_type'),
                'object_id': audit_info.get('object_id'),
                'ip_address': audit_info['ip_address'],
                'user_agent': audit_info['user_agent']
            })
            
            # Сохраняем в базу данных (импортируем здесь чтобы избежать циклических импортов)
            try:
                from .models import ContentAuditLog
                ContentAuditLog.log_action(
                    user=audit_info['user'],
                    action=audit_info['action'],
                    object_type=audit_info.get('object_type', ''),
                    object_id=audit_info.get('object_id'),
                    ip_address=audit_info['ip_address'],
                    user_agent=audit_info['user_agent']
                )
            except Exception as e:
                logger.error(f"Failed to save audit log to database: {e}")
        
        return response
    
    def _get_action_info(self, request, view_func, view_kwargs):
        """Определяет тип действия на основе URL и метода запроса"""
        
        view_name = getattr(view_func, '__name__', '')
        method = request.method
        
        # Определяем действия для текстового контента
        if 'TextEditorView' in str(view_func):
            text_id = view_kwargs.get('text_id')
            if method == 'POST':
                if text_id:
                    return {
                        'action': 'update_text_content',
                        'object_type': 'TextContent',
                        'object_id': text_id
                    }
                else:
                    return {
                        'action': 'create_text_content',
                        'object_type': 'TextContent'
                    }
            elif method == 'GET' and text_id:
                return {
                    'action': 'view_text_content',
                    'object_type': 'TextContent',
                    'object_id': text_id
                }
        
        # Определяем действия для автосохранения
        elif 'AutosaveView' in str(view_func):
            return {
                'action': 'autosave_text_content',
                'object_type': 'TextContent'
            }
        
        # Определяем действия для проектов
        elif view_name == 'create_project':
            if method == 'POST':
                return {
                    'action': 'create_project',
                    'object_type': 'Project'
                }
        
        elif view_name == 'project_texts':
            project_id = view_kwargs.get('project_id')
            return {
                'action': 'view_project_texts',
                'object_type': 'Project',
                'object_id': project_id
            }
        
        # Определяем действия для галереи изображений
        elif 'ImageGalleryView' in str(view_func):
            project_id = view_kwargs.get('project_id')
            return {
                'action': 'view_image_gallery',
                'object_type': 'Project',
                'object_id': project_id
            }
        
        return None
    
    def _get_client_ip(self, request):
        """Получает IP адрес клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ContentActionLogger:
    """Утилитный класс для логирования специфических действий с контентом"""
    
    @staticmethod
    def log_text_created(user, text_content):
        """Логирует создание нового текста"""
        logger.info(
            f"Text content created: '{text_content.title}' by {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'action': 'text_created',
                'text_id': text_content.id,
                'text_title': text_content.title,
                'project_id': text_content.project.id,
                'project_name': text_content.project.name,
                'team_id': text_content.project.team.id,
                'team_name': text_content.project.team.name
            }
        )
        
        # Сохраняем в базу данных
        try:
            from .models import ContentAuditLog
            ContentAuditLog.log_action(
                user=user,
                action='create_text',
                object_type='TextContent',
                object_id=text_content.id,
                details={
                    'title': text_content.title,
                    'project_id': text_content.project.id,
                    'project_name': text_content.project.name,
                    'team_name': text_content.project.team.name
                }
            )
        except Exception as e:
            logger.error(f"Failed to save text creation audit log: {e}")
    
    @staticmethod
    def log_text_updated(user, text_content, fields_changed=None):
        """Логирует обновление текста"""
        message = f"Text content updated: '{text_content.title}' by {user.username}"
        if fields_changed:
            message += f" (fields: {', '.join(fields_changed)})"
        
        logger.info(message, extra={
            'user_id': user.id,
            'username': user.username,
            'action': 'text_updated',
            'text_id': text_content.id,
            'text_title': text_content.title,
            'project_id': text_content.project.id,
            'fields_changed': fields_changed or []
        })
        
        # Сохраняем в базу данных
        try:
            from .models import ContentAuditLog
            ContentAuditLog.log_action(
                user=user,
                action='update_text',
                object_type='TextContent',
                object_id=text_content.id,
                details={
                    'title': text_content.title,
                    'fields_changed': fields_changed or [],
                    'project_id': text_content.project.id
                }
            )
        except Exception as e:
            logger.error(f"Failed to save text update audit log: {e}")
    
    @staticmethod
    def log_text_autosaved(user, text_content):
        """Логирует автосохранение текста"""
        logger.debug(
            f"Text content autosaved: '{text_content.title}' by {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'action': 'text_autosaved',
                'text_id': text_content.id,
                'text_title': text_content.title
            }
        )
    
    @staticmethod
    def log_project_created(user, project):
        """Логирует создание нового проекта"""
        logger.info(
            f"Project created: '{project.name}' by {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'action': 'project_created',
                'project_id': project.id,
                'project_name': project.name,
                'team_id': project.team.id,
                'team_name': project.team.name
            }
        )
        
        # Сохраняем в базу данных
        try:
            from .models import ContentAuditLog
            ContentAuditLog.log_action(
                user=user,
                action='create_project',
                object_type='Project',
                object_id=project.id,
                details={
                    'name': project.name,
                    'team_id': project.team.id,
                    'team_name': project.team.name,
                    'content_folder': project.content_folder
                },
                user_agent='Django Application'  # Заглушка для случаев без HTTP запроса
            )
        except Exception as e:
            logger.error(f"Failed to save project creation audit log: {e}")
    
    @staticmethod
    def log_image_uploaded(user, image_content):
        """Логирует загрузку изображения"""
        logger.info(
            f"Image uploaded: '{image_content.title}' by {user.username}",
            extra={
                'user_id': user.id,
                'username': user.username,
                'action': 'image_uploaded',
                'image_id': image_content.id,
                'image_title': image_content.title,
                'project_id': image_content.project.id,
                'file_size': image_content.file_size
            }
        )
    
    @staticmethod
    def log_access_denied(user, action, object_type, object_id=None):
        """Логирует попытки несанкционированного доступа"""
        message = f"Access denied: {user.username} tried to {action} {object_type}"
        if object_id:
            message += f" ID {object_id}"
        
        logger.warning(message, extra={
            'user_id': user.id,
            'username': user.username,
            'action': 'access_denied',
            'attempted_action': action,
            'object_type': object_type,
            'object_id': object_id
        })
        
        # Сохраняем в базу данных
        try:
            from .models import ContentAuditLog
            ContentAuditLog.log_action(
                user=user,
                action='access_denied',
                object_type=object_type,
                object_id=object_id,
                details={
                    'attempted_action': action,
                    'reason': 'insufficient_permissions'
                }
            )
        except Exception as e:
            logger.error(f"Failed to save access denied audit log: {e}")