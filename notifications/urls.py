from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('<int:pk>/mark-read/', views.MarkNotificationReadView.as_view(), name='mark_read'),
    path('mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='mark_all_read'),
    path('preferences/', views.NotificationPreferencesView.as_view(), name='preferences'),
    path('api/unread-count/', views.GetUnreadCountView.as_view(), name='unread_count'),
]