from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from .views import MainPageView, DocsView, TestDropdownView, TestDjangoView

# Импортируем наш расширенный административный сайт
from utils.admin_site import admin_site

urlpatterns = [
    path('admin/', admin_site.urls),
    # URL-маршруты для управления командами
    path('teams/', include('teams.urls', namespace='teams')),
    # URL-маршруты пользователей (аутентификация)
    path('accounts/', include('users.urls')),
    # URL-маршруты для управления проектами
    path('projects/', include('projects.urls', namespace='projects')),
    # URL-маршруты для глоссария
    path('glossary/', include('glossary.urls', namespace='glossary')),
    # URL-маршруты для системы уведомлений
    path('notifications/', include('notifications.urls', namespace='notifications')),
    # URL-маршруты для TinyMCE редактора
    path('tinymce/', include('tinymce.urls')),
    # URL-маршруты для редактора контента
    path('content/', include('content.urls', namespace='content')),
    # Обработка favicon
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico', permanent=True)),
    # Главная страница сайта
    path('', MainPageView.as_view(), name='main_page'),
    # Страница документации
    path('docs/', DocsView.as_view(), name='docs'),
    # Тестовая страница для dropdown
    path('test-dropdown/', TestDropdownView.as_view(), name='test_dropdown'),
    # Тестовая страница для Django template
    path('test-django/', TestDjangoView.as_view(), name='test_django'),
]

# Обслуживание медиафайлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)