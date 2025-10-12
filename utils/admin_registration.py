"""
Регистрация административных интерфейсов для файловой системы.
"""

from django.contrib import admin
from django.urls import path, include
from django.utils.html import format_html
from django.contrib.admin import AdminSite

from .admin import FileSystemAdminView
from .admin_monitoring import FileMonitoringAdmin


class FileSystemAdmin(admin.ModelAdmin):
    """Фиктивная модель для отображения файловой системы в админке"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_staff
    
    def changelist_view(self, request, extra_context=None):
        """Переопределяем представление списка для показа файловой системы"""
        file_system_admin = FileSystemAdminView()
        return file_system_admin.file_structure_view(request)


# Создаем экземпляры административных интерфейсов
file_system_admin = FileSystemAdminView()
file_monitoring_admin = FileMonitoringAdmin()


def get_file_system_urls():
    """Получить URL-ы для файловой системы"""
    urls = []
    
    # URL-ы основного интерфейса
    urls.extend(file_system_admin.get_urls())
    
    # URL-ы мониторинга
    urls.extend(file_monitoring_admin.get_urls())
    
    return urls


def register_file_system_admin():
    """Регистрация административных интерфейсов файловой системы"""
    
    # Добавляем URL-ы в админку
    original_get_urls = AdminSite.get_urls
    
    def get_urls_with_file_system(self):
        urls = original_get_urls(self)
        file_system_urls = get_file_system_urls()
        return file_system_urls + urls
    
    AdminSite.get_urls = get_urls_with_file_system


def add_file_system_to_admin_index():
    """Добавить ссылки на файловую систему в главное меню админки"""
    
    def file_system_admin_context(request):
        """Контекстный процессор для добавления ссылок на файловую систему"""
        if request.user.is_staff:
            return {
                'file_system_links': [
                    {
                        'title': 'Структура файлов',
                        'url': '/admin/file-structure/',
                        'description': 'Просмотр иерархической структуры файлов'
                    },
                    {
                        'title': 'Статистика файлов',
                        'url': '/admin/file-statistics/',
                        'description': 'Статистика использования файлов по пользователям, командам и проектам'
                    },
                    {
                        'title': 'Диагностика файлов',
                        'url': '/admin/file-diagnostics/',
                        'description': 'Поиск проблем с файлами и структурой'
                    },
                    {
                        'title': 'Управление файлами',
                        'url': '/admin/file-management/',
                        'description': 'Инструменты для управления и очистки файлов'
                    },
                    {
                        'title': 'Статус системы',
                        'url': '/admin/file-system-status/',
                        'description': 'Общий статус файловой системы'
                    },
                    {
                        'title': 'Метрики файлов',
                        'url': '/admin/file-metrics/',
                        'description': 'Детальные метрики использования файлов'
                    }
                ]
            }
        return {}
    
    return file_system_admin_context


# Инициализация
register_file_system_admin()