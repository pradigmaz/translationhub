"""
Сервисы для работы с уведомлениями
"""

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from .models import Notification, NotificationType, UserNotificationPreferences

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:
    """Сервис для отправки уведомлений"""
    
    @staticmethod
    def send_team_status_notification(team, change_type, changed_by, reason=""):
        """
        Отправляет уведомления об изменении статуса команды
        
        Args:
            team: Объект команды
            change_type: Тип изменения (TeamStatusChangeType)
            changed_by: Пользователь, выполнивший изменение
            reason: Причина изменения
        """
        from teams.models import TeamStatusChangeType
        
        # Определяем тип уведомления
        notification_type_map = {
            TeamStatusChangeType.DEACTIVATED: NotificationType.TEAM_DEACTIVATED,
            TeamStatusChangeType.REACTIVATED: NotificationType.TEAM_REACTIVATED,
            TeamStatusChangeType.DISBANDED: NotificationType.TEAM_DISBANDED,
        }
        
        notification_type = notification_type_map.get(change_type)
        if not notification_type:
            logger.warning(f"Неизвестный тип изменения статуса команды: {change_type}")
            return
        
        # Получаем всех участников команды (кроме того, кто выполнил действие)
        from teams.models import TeamMembership
        recipients = User.objects.filter(
            teammembership__team=team
        ).exclude(id=changed_by.id).distinct()
        
        # Генерируем заголовок и сообщение
        title_map = {
            NotificationType.TEAM_DEACTIVATED: f'Команда "{team.name}" приостановлена',
            NotificationType.TEAM_REACTIVATED: f'Команда "{team.name}" возобновлена',
            NotificationType.TEAM_DISBANDED: f'Команда "{team.name}" распущена',
        }
        
        message_map = {
            NotificationType.TEAM_DEACTIVATED: f'Руководитель {changed_by.username} приостановил работу команды "{team.name}". Функции управления ограничены до возобновления работы.',
            NotificationType.TEAM_REACTIVATED: f'Руководитель {changed_by.username} возобновил работу команды "{team.name}". Все функции снова доступны.',
            NotificationType.TEAM_DISBANDED: f'Руководитель {changed_by.username} распустил команду "{team.name}". Все участники исключены из команды.',
        }
        
        title = title_map[notification_type]
        message = message_map[notification_type]
        
        if reason:
            message += f' Причина: {reason}'
        
        # Дополнительные данные
        extra_data = {
            'team_id': team.id,
            'team_name': team.name,
            'changed_by_id': changed_by.id,
            'changed_by_username': changed_by.username,
            'change_type': change_type,
            'reason': reason,
        }
        
        # Отправляем уведомления всем участникам
        for recipient in recipients:
            NotificationService._create_and_send_notification(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data=extra_data
            )
        
        logger.info(f"Отправлены уведомления об изменении статуса команды {team.name} "
                   f"({change_type}) для {recipients.count()} участников")
    
    @staticmethod
    def _create_and_send_notification(recipient, notification_type, title, message, extra_data=None):
        """
        Создает уведомление и отправляет его пользователю
        
        Args:
            recipient: Получатель уведомления
            notification_type: Тип уведомления
            title: Заголовок
            message: Сообщение
            extra_data: Дополнительные данные
        """
        if extra_data is None:
            extra_data = {}
        
        # Получаем настройки уведомлений пользователя
        preferences = UserNotificationPreferences.get_or_create_for_user(recipient)
        
        # Проверяем, нужно ли отправлять веб-уведомление
        web_notification_enabled = NotificationService._should_send_web_notification(
            preferences, notification_type
        )
        
        if web_notification_enabled:
            # Создаем веб-уведомление
            notification = Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                extra_data=extra_data
            )
            logger.debug(f"Создано веб-уведомление {notification.id} для {recipient.username}")
        
        # Проверяем, нужно ли отправлять email-уведомление
        email_notification_enabled = NotificationService._should_send_email_notification(
            preferences, notification_type
        )
        
        if email_notification_enabled and recipient.email:
            NotificationService._send_email_notification(
                recipient, notification_type, title, message, extra_data
            )
    
    @staticmethod
    def _should_send_web_notification(preferences, notification_type):
        """Проверяет, нужно ли отправлять веб-уведомление"""
        web_settings_map = {
            NotificationType.TEAM_DEACTIVATED: preferences.web_team_status_changes,
            NotificationType.TEAM_REACTIVATED: preferences.web_team_status_changes,
            NotificationType.TEAM_DISBANDED: preferences.web_team_status_changes,
            NotificationType.TEAM_INVITATION: preferences.web_team_invitations,
            NotificationType.TASK_ASSIGNED: preferences.web_task_assignments,
            NotificationType.PROJECT_UPDATE: preferences.web_project_updates,
            NotificationType.COMMENT_MENTION: preferences.web_comment_mentions,
        }
        return web_settings_map.get(notification_type, True)
    
    @staticmethod
    def _should_send_email_notification(preferences, notification_type):
        """Проверяет, нужно ли отправлять email-уведомление"""
        email_settings_map = {
            NotificationType.TEAM_DEACTIVATED: preferences.email_team_status_changes,
            NotificationType.TEAM_REACTIVATED: preferences.email_team_status_changes,
            NotificationType.TEAM_DISBANDED: preferences.email_team_status_changes,
            NotificationType.TEAM_INVITATION: preferences.email_team_invitations,
            NotificationType.TASK_ASSIGNED: preferences.email_task_assignments,
            NotificationType.PROJECT_UPDATE: preferences.email_project_updates,
            NotificationType.COMMENT_MENTION: preferences.email_comment_mentions,
        }
        return email_settings_map.get(notification_type, True)
    
    @staticmethod
    def _send_email_notification(recipient, notification_type, title, message, extra_data):
        """Отправляет email-уведомление"""
        try:
            # Определяем шаблон для email
            template_map = {
                NotificationType.TEAM_DEACTIVATED: 'notifications/email/team_deactivated.html',
                NotificationType.TEAM_REACTIVATED: 'notifications/email/team_reactivated.html',
                NotificationType.TEAM_DISBANDED: 'notifications/email/team_disbanded.html',
                NotificationType.TEAM_INVITATION: 'notifications/email/team_invitation.html',
                NotificationType.TASK_ASSIGNED: 'notifications/email/task_assigned.html',
                NotificationType.PROJECT_UPDATE: 'notifications/email/project_update.html',
                NotificationType.COMMENT_MENTION: 'notifications/email/comment_mention.html',
            }
            
            template_name = template_map.get(notification_type, 'notifications/email/default.html')
            
            # Контекст для шаблона
            context = {
                'recipient': recipient,
                'title': title,
                'message': message,
                'extra_data': extra_data,
                'site_name': getattr(settings, 'SITE_NAME', 'MangaCollab'),
            }
            
            # Рендерим HTML и текстовую версию
            html_message = render_to_string(template_name, context)
            text_message = render_to_string(
                template_name.replace('.html', '.txt'), 
                context
            )
            
            # Отправляем email
            send_mail(
                subject=f"[MangaCollab] {title}",
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Отправлено email-уведомление для {recipient.username} ({recipient.email})")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке email-уведомления для {recipient.username}: {e}")
    
    @staticmethod
    def get_unread_count(user):
        """Возвращает количество непрочитанных уведомлений пользователя"""
        return Notification.objects.filter(recipient=user, is_read=False).count()
    
    @staticmethod
    def mark_all_as_read(user):
        """Отмечает все уведомления пользователя как прочитанные"""
        count = Notification.objects.filter(recipient=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        logger.info(f"Отмечено как прочитанные {count} уведомлений для {user.username}")
        return count