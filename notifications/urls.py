from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # URL-маршруты будут добавлены при реализации представлений
    # path('', views.NotificationListView.as_view(), name='notification_list'),
    # path('<int:pk>/mark-read/', views.MarkNotificationReadView.as_view(), name='mark_read'),
]