"""
Расширенный административный сайт с поддержкой файловой системы.
"""

from django.contrib import admin
from django.urls import path
from django.utils.html import format_html
from django.template.response import TemplateResponse

from .admin import FileSystemAdminView
from .admin_monitoring import FileMonitoringAdmin


class FileSystemAdminSite(admin.AdminSite):
    """Расширенный административный сайт с поддержкой файловой системы"""
    
    site_header = "TranslationHub - Административная панель"
    site_title = "TranslationHub Admin"
    index_title = "Панель управления"
    
    def __init__(self, name='admin'):
        super().__init__(name)
        self.file_system_admin = FileSystemAdminView()
        self.file_monitoring_admin = FileMonitoringAdmin()
        self.file_monitoring_admin.admin_site = self
    
    def get_urls(self):
        """Получить URL-ы с добавлением файловой системы"""
        urls = super().get_urls()
        
        # Добавляем URL-ы файловой системы
        file_system_urls = [
            path('file-structure/', self.admin_view(self.file_system_admin.file_structure_view), name='file_structure'),
            path('file-statistics/', self.admin_view(self.file_system_admin.file_statistics_view), name='file_statistics'),
            path('file-diagnostics/', self.admin_view(self.file_system_admin.file_diagnostics_view), name='file_diagnostics'),
            path('file-management/', self.admin_view(self.file_system_admin.file_management_view), name='file_management'),
            path('file-system-status/', self.admin_view(self.file_system_admin.file_system_status_view), name='file_system_status'),
            path('file-system-health/', self.admin_view(self.file_system_admin.file_system_health_view), name='file_system_health'),
            
            # API endpoints
            path('api/file-tree/', self.admin_view(self.file_system_admin.api_file_tree), name='api_file_tree'),
            path('api/cleanup-orphaned/', self.admin_view(self.file_system_admin.api_cleanup_orphaned), name='api_cleanup_orphaned'),
            path('api/fix-permissions/', self.admin_view(self.file_system_admin.api_fix_permissions), name='api_fix_permissions'),
            path('api/validate-structure/', self.admin_view(self.file_system_admin.api_validate_structure), name='api_validate_structure'),
        ]
        
        # Добавляем URL-ы мониторинга
        monitoring_urls = [
            path('file-metrics/', self.admin_view(self.file_monitoring_admin.file_metrics_view), name='file_metrics'),
            path('operation-stats/', self.admin_view(self.file_monitoring_admin.operation_stats_view), name='operation_stats'),
            path('cleanup-orphaned/', self.admin_view(self.file_monitoring_admin.cleanup_orphaned_view), name='cleanup_orphaned'),
            path('api/metrics/', self.admin_view(self.file_monitoring_admin.api_metrics), name='api_metrics'),
            path('api/cleanup/', self.admin_view(self.file_monitoring_admin.api_cleanup), name='api_cleanup'),
        ]
        
        return file_system_urls + monitoring_urls + urls
    
    def index(self, request, extra_context=None):
        """Расширенная главная страница админки с информацией о файловой системе"""
        extra_context = extra_context or {}
        
        # Добавляем информацию о файловой системе
        try:
            from utils.file_monitoring import file_metrics
            from utils.admin_helpers import FileSystemAdminHelpers
            
            # Получаем базовые метрики
            disk_usage = file_metrics.get_disk_usage()
            structure_stats = FileSystemAdminHelpers.get_structure_statistics()
            
            extra_context.update({
                'file_system_info': {
                    'disk_usage': disk_usage,
                    'structure_stats': structure_stats,
                    'has_warnings': (
                        disk_usage.get('percent_used', 0) > 80 or
                        len(structure_stats.get('missing_user_dirs', [])) > 0 or
                        len(structure_stats.get('missing_team_dirs', [])) > 0 or
                        len(structure_stats.get('missing_project_dirs', [])) > 0
                    )
                },
                'file_system_links': [
                    {
                        'title': 'Структура файлов',
                        'url': 'file-structure/',
                        'description': 'Просмотр иерархической структуры файлов',
                        'icon': '📁'
                    },
                    {
                        'title': 'Статистика файлов',
                        'url': 'file-statistics/',
                        'description': 'Статистика использования файлов',
                        'icon': '📊'
                    },
                    {
                        'title': 'Диагностика',
                        'url': 'file-diagnostics/',
                        'description': 'Поиск проблем с файлами',
                        'icon': '🔍'
                    },
                    {
                        'title': 'Управление файлами',
                        'url': 'file-management/',
                        'description': 'Инструменты управления файлами',
                        'icon': '🛠'
                    },
                    {
                        'title': 'Статус системы',
                        'url': 'file-system-status/',
                        'description': 'Общий статус файловой системы',
                        'icon': '💾'
                    },
                    {
                        'title': 'Метрики',
                        'url': 'file-metrics/',
                        'description': 'Детальные метрики файлов',
                        'icon': '📈'
                    }
                ]
            })
            
        except Exception as e:
            extra_context['file_system_error'] = str(e)
        
        return super().index(request, extra_context)


# Создаем экземпляр расширенного административного сайта
admin_site = FileSystemAdminSite()

# Регистрируем все модели из стандартного сайта
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin

admin_site.register(User, UserAdmin)
admin_site.register(Group, GroupAdmin)

# Регистрируем модели приложений
def register_app_models():
    """Регистрация моделей всех приложений"""
    
    # Users
    try:
        from users.models import User as CustomUser
        from users.admin import UserAdmin as CustomUserAdmin
        admin_site.register(CustomUser, CustomUserAdmin)
    except:
        pass
    
    # Teams
    try:
        from teams.models import Team, TeamMembership, Role, TeamStatusHistory
        from teams.admin import TeamAdmin, TeamMembershipAdmin, TeamStatusHistoryAdmin
        admin_site.register(Team, TeamAdmin)
        admin_site.register(TeamMembership, TeamMembershipAdmin)
        admin_site.register(Role)  # Simple registration
        admin_site.register(TeamStatusHistory, TeamStatusHistoryAdmin)
    except:
        pass
    
    # Projects
    try:
        from projects.models import Project, Chapter
        from projects.admin import ProjectAdmin, ChapterAdmin
        admin_site.register(Project, ProjectAdmin)
        admin_site.register(Chapter, ChapterAdmin)
    except:
        pass
    
    # Content
    try:
        from content.models import TextContent, ImageContent, ProjectDocument, ContentAuditLog
        from content.admin import TextContentAdmin, ImageContentAdmin, ProjectDocumentAdmin, ContentAuditLogAdmin
        admin_site.register(TextContent, TextContentAdmin)
        admin_site.register(ImageContent, ImageContentAdmin)
        admin_site.register(ProjectDocument, ProjectDocumentAdmin)
        admin_site.register(ContentAuditLog, ContentAuditLogAdmin)
    except:
        pass
    
    # Glossary
    try:
        from glossary.models import GlossaryTerm
        admin_site.register(GlossaryTerm)
    except:
        pass
    
    # Notifications
    try:
        from notifications.models import Notification
        admin_site.register(Notification)
    except:
        pass

# Регистрируем модели
register_app_models()