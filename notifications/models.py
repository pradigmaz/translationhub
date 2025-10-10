from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class NotificationType(models.TextChoices):
    """Типы уведомлений"""
    TEAM_DEACTIVATED = 'team_deactivated', 'Команда приостановлена'
    TEAM_REACTIVATED = 'team_reactivated', 'Команда возобновлена'
    TEAM_DISBANDED = 'team_disbanded', 'Команда распущена'
    TEAM_INVITATION = 'team_invitation', 'Приглашение в команду'
    TASK_ASSIGNED = 'task_assigned', 'Назначена задача'
    PROJECT_UPDATE = 'project_update', 'Обновление проекта'
    COMMENT_MENTION = 'comment_mention', 'Упоминание в комментарии'


class Notification(models.Model):
    """Модель уведомления"""
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Получатель'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        verbose_name='Тип уведомления'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Заголовок'
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    
    # Дополнительные данные в JSON формате
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Дополнительные данные'
    )
    
    # Статус уведомления
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано'
    )
    
    # Временные метки
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Прочитано в'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
    
    def __str__(self):
        return f"{self.title} для {self.recipient.username}"
    
    def mark_as_read(self):
        """Отмечает уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class UserNotificationPreferences(models.Model):
    """Настройки уведомлений пользователя"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
        verbose_name='Пользователь'
    )
    
    # Email уведомления
    email_team_status_changes = models.BooleanField(
        default=True,
        verbose_name='Email при изменении статуса команды'
    )
    email_team_invitations = models.BooleanField(
        default=True,
        verbose_name='Email при приглашениях в команды'
    )
    email_task_assignments = models.BooleanField(
        default=True,
        verbose_name='Email при назначении задач'
    )
    email_project_updates = models.BooleanField(
        default=False,
        verbose_name='Email при обновлениях проектов'
    )
    email_comment_mentions = models.BooleanField(
        default=True,
        verbose_name='Email при упоминаниях в комментариях'
    )
    
    # Веб уведомления (в интерфейсе)
    web_team_status_changes = models.BooleanField(
        default=True,
        verbose_name='Веб уведомления об изменении статуса команды'
    )
    web_team_invitations = models.BooleanField(
        default=True,
        verbose_name='Веб уведомления о приглашениях в команды'
    )
    web_task_assignments = models.BooleanField(
        default=True,
        verbose_name='Веб уведомления о назначении задач'
    )
    web_project_updates = models.BooleanField(
        default=True,
        verbose_name='Веб уведомления об обновлениях проектов'
    )
    web_comment_mentions = models.BooleanField(
        default=True,
        verbose_name='Веб уведомления об упоминаниях в комментариях'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Настройки уведомлений'
        verbose_name_plural = 'Настройки уведомлений'
    
    def __str__(self):
        return f"Настройки уведомлений для {self.user.username}"
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Получает или создает настройки уведомлений для пользователя"""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'email_team_status_changes': True,
                'email_team_invitations': True,
                'email_task_assignments': True,
                'email_project_updates': False,
                'email_comment_mentions': True,
                'web_team_status_changes': True,
                'web_team_invitations': True,
                'web_task_assignments': True,
                'web_project_updates': True,
                'web_comment_mentions': True,
            }
        )
        return preferences
