from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, View
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Notification, UserNotificationPreferences
from .services import NotificationService


class NotificationListView(LoginRequiredMixin, ListView):
    """Список уведомлений пользователя"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        """Получаем уведомления текущего пользователя"""
        queryset = Notification.objects.filter(recipient=self.request.user)
        
        # Фильтрация по статусу прочтения
        status_filter = self.request.GET.get('status')
        if status_filter == 'unread':
            queryset = queryset.filter(is_read=False)
        elif status_filter == 'read':
            queryset = queryset.filter(is_read=True)
        
        # Фильтрация по типу уведомления
        type_filter = self.request.GET.get('type')
        if type_filter:
            queryset = queryset.filter(notification_type=type_filter)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Статистика уведомлений
        user_notifications = Notification.objects.filter(recipient=self.request.user)
        context['unread_count'] = user_notifications.filter(is_read=False).count()
        context['total_count'] = user_notifications.count()
        
        # Текущие фильтры
        context['current_status_filter'] = self.request.GET.get('status', 'all')
        context['current_type_filter'] = self.request.GET.get('type', 'all')
        
        return context


class MarkNotificationReadView(LoginRequiredMixin, View):
    """Отметка уведомления как прочитанного"""
    
    def post(self, request, pk):
        """Отмечает уведомление как прочитанное"""
        notification = get_object_or_404(
            Notification, 
            pk=pk, 
            recipient=request.user
        )
        
        notification.mark_as_read()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Уведомление отмечено как прочитанное'
            })
        
        messages.success(request, 'Уведомление отмечено как прочитанное')
        return redirect('notifications:notification_list')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    """Отметка всех уведомлений как прочитанных"""
    
    def post(self, request):
        """Отмечает все уведомления пользователя как прочитанные"""
        count = NotificationService.mark_all_as_read(request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Отмечено как прочитанные {count} уведомлений',
                'count': count
            })
        
        messages.success(request, f'Отмечено как прочитанные {count} уведомлений')
        return redirect('notifications:notification_list')


class NotificationPreferencesView(LoginRequiredMixin, View):
    """Управление настройками уведомлений"""
    
    def get(self, request):
        """Отображает форму настроек уведомлений"""
        preferences = UserNotificationPreferences.get_or_create_for_user(request.user)
        
        context = {
            'preferences': preferences,
        }
        
        return render(request, 'notifications/preferences.html', context)
    
    def post(self, request):
        """Сохраняет настройки уведомлений"""
        preferences = UserNotificationPreferences.get_or_create_for_user(request.user)
        
        # Обновляем настройки email уведомлений
        preferences.email_team_status_changes = 'email_team_status_changes' in request.POST
        preferences.email_team_invitations = 'email_team_invitations' in request.POST
        preferences.email_task_assignments = 'email_task_assignments' in request.POST
        preferences.email_project_updates = 'email_project_updates' in request.POST
        preferences.email_comment_mentions = 'email_comment_mentions' in request.POST
        
        # Обновляем настройки веб уведомлений
        preferences.web_team_status_changes = 'web_team_status_changes' in request.POST
        preferences.web_team_invitations = 'web_team_invitations' in request.POST
        preferences.web_task_assignments = 'web_task_assignments' in request.POST
        preferences.web_project_updates = 'web_project_updates' in request.POST
        preferences.web_comment_mentions = 'web_comment_mentions' in request.POST
        
        preferences.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Настройки уведомлений сохранены'
            })
        
        messages.success(request, 'Настройки уведомлений сохранены')
        return redirect('notifications:preferences')


class GetUnreadCountView(LoginRequiredMixin, View):
    """API для получения количества непрочитанных уведомлений"""
    
    def get(self, request):
        """Возвращает количество непрочитанных уведомлений"""
        count = NotificationService.get_unread_count(request.user)
        
        return JsonResponse({
            'unread_count': count
        })
