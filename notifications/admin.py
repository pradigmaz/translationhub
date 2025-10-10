from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from .models import Notification, UserNotificationPreferences, NotificationType


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Административный интерфейс для уведомлений"""
    
    list_display = ('title', 'recipient', 'notification_type_display', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username', 'recipient__email')
    readonly_fields = ('created_at', 'read_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Дополнительные данные', {
            'fields': ('extra_data',),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_read', 'created_at', 'read_at')
        }),
    )
    
    def notification_type_display(self, obj):
        """Отображение типа уведомления с цветовой индикацией"""
        colors = {
            NotificationType.TEAM_DEACTIVATED: 'orange',
            NotificationType.TEAM_REACTIVATED: 'green',
            NotificationType.TEAM_DISBANDED: 'red',
            NotificationType.TEAM_INVITATION: 'blue',
            NotificationType.TASK_ASSIGNED: 'purple',
            NotificationType.PROJECT_UPDATE: 'teal',
            NotificationType.COMMENT_MENTION: 'gray',
        }
        
        color = colors.get(obj.notification_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_notification_type_display()
        )
    notification_type_display.short_description = 'Тип уведомления'
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        """Массовая отметка уведомлений как прочитанных"""
        count = 0
        for notification in queryset.filter(is_read=False):
            notification.mark_as_read()
            count += 1
        
        self.message_user(request, f'Отмечено как прочитанные {count} уведомлений')
    mark_as_read.short_description = 'Отметить как прочитанные'
    
    def mark_as_unread(self, request, queryset):
        """Массовая отметка уведомлений как непрочитанных"""
        count = queryset.filter(is_read=True).update(
            is_read=False,
            read_at=None
        )
        
        self.message_user(request, f'Отмечено как непрочитанные {count} уведомлений')
    mark_as_unread.short_description = 'Отметить как непрочитанные'


@admin.register(UserNotificationPreferences)
class UserNotificationPreferencesAdmin(admin.ModelAdmin):
    """Административный интерфейс для настроек уведомлений"""
    
    list_display = ('user', 'email_notifications_summary', 'web_notifications_summary', 'updated_at')
    list_filter = ('email_team_status_changes', 'web_team_status_changes', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Email уведомления', {
            'fields': (
                'email_team_status_changes',
                'email_team_invitations',
                'email_task_assignments',
                'email_project_updates',
                'email_comment_mentions',
            )
        }),
        ('Веб уведомления', {
            'fields': (
                'web_team_status_changes',
                'web_team_invitations',
                'web_task_assignments',
                'web_project_updates',
                'web_comment_mentions',
            )
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def email_notifications_summary(self, obj):
        """Краткая сводка по email уведомлениям"""
        enabled_count = sum([
            obj.email_team_status_changes,
            obj.email_team_invitations,
            obj.email_task_assignments,
            obj.email_project_updates,
            obj.email_comment_mentions,
        ])
        
        color = 'green' if enabled_count > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}/5 включено</span>',
            color,
            enabled_count
        )
    email_notifications_summary.short_description = 'Email уведомления'
    
    def web_notifications_summary(self, obj):
        """Краткая сводка по веб уведомлениям"""
        enabled_count = sum([
            obj.web_team_status_changes,
            obj.web_team_invitations,
            obj.web_task_assignments,
            obj.web_project_updates,
            obj.web_comment_mentions,
        ])
        
        color = 'green' if enabled_count > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}/5 включено</span>',
            color,
            enabled_count
        )
    web_notifications_summary.short_description = 'Веб уведомления'
