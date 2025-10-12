"""
Django админка для мониторинга файловых операций.

Предоставляет интерфейс для просмотра состояния файловой системы
и управления файловыми операциями.
"""

from django.contrib import admin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Sum
from django.core.paginator import Paginator
import json
import os
from pathlib import Path

from utils.file_system import FilePathManager, DirectoryManager, FileCleanupManager, FileOperationLogger
from utils.file_monitoring import file_metrics, operation_monitor, orphaned_cleanup
from users.models import User
from teams.models import Team
from projects.models import Project
from content.models import ImageContent, ProjectDocument


class FileSystemAdminView:
    """Административный интерфейс для файловой системы"""
    
    def get_urls(self):
        """Получить URL-ы для административного интерфейса"""
        urls = [
            path('file-system-status/', self.file_system_status_view, name='file_system_status'),
            path('file-system-health/', self.file_system_health_view, name='file_system_health'),
            path('file-structure/', self.file_structure_view, name='file_structure'),
            path('file-statistics/', self.file_statistics_view, name='file_statistics'),
            path('file-diagnostics/', self.file_diagnostics_view, name='file_diagnostics'),
            path('file-management/', self.file_management_view, name='file_management'),
            path('api/file-tree/', self.api_file_tree, name='api_file_tree'),
            path('api/cleanup-orphaned/', self.api_cleanup_orphaned, name='api_cleanup_orphaned'),
            path('api/fix-permissions/', self.api_fix_permissions, name='api_fix_permissions'),
            path('api/validate-structure/', self.api_validate_structure, name='api_validate_structure'),
        ]
        return urls
    
    @staff_member_required
    def file_system_status_view(self, request):
        """Представление для отображения состояния файловой системы"""
        try:
            health_report = file_metrics.get_cached_metrics()
            
            context = {
                'title': 'File System Status',
                'health_report': health_report,
                'has_warnings': bool(health_report.get('warnings')),
                'has_errors': 'error' in health_report,
            }
            
            return render(request, 'admin/utils/file_system_status.html', context)
            
        except Exception as e:
            FileOperationLogger.log_error("admin_file_system_status", e, notify_admins=True)
            context = {
                'title': 'File System Status',
                'error': str(e),
                'has_errors': True,
            }
            return render(request, 'admin/utils/file_system_status.html', context)
    
    @staff_member_required
    def file_system_health_view(self, request):
        """API endpoint для получения данных о состоянии файловой системы"""
        try:
            health_report = file_metrics.get_cached_metrics()
            return JsonResponse(health_report)
            
        except Exception as e:
            FileOperationLogger.log_error("admin_file_system_health_api", e)
            return JsonResponse({
                'error': str(e),
                'warnings': ['Failed to get system health data']
            }, status=500)
    
    @staff_member_required
    def file_structure_view(self, request):
        """Представление для отображения файловой структуры"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        context = {
            'title': 'Файловая структура',
            'has_permission': True,
        }
        
        try:
            # Получаем структуру файлов
            file_tree = FileSystemAdminHelpers.build_file_tree()
            context['file_tree'] = file_tree
            context['file_tree_json'] = json.dumps(file_tree, default=str, ensure_ascii=False)
            
            # Статистика по структуре
            structure_stats = FileSystemAdminHelpers.get_structure_statistics()
            context['structure_stats'] = structure_stats
            
        except Exception as e:
            messages.error(request, f'Ошибка получения файловой структуры: {e}')
            context['error'] = str(e)
        
        return render(request, 'admin/utils/file_structure.html', context)
    
    @staff_member_required
    def file_statistics_view(self, request):
        """Представление для отображения статистики использования файлов"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        context = {
            'title': 'Статистика использования файлов',
            'has_permission': True,
        }
        
        try:
            # Общая статистика
            general_stats = FileSystemAdminHelpers.get_general_file_statistics()
            context['general_stats'] = general_stats
            
            # Статистика по пользователям
            user_stats = FileSystemAdminHelpers.get_user_file_statistics()
            context['user_stats'] = user_stats
            
            # Статистика по командам
            team_stats = FileSystemAdminHelpers.get_team_file_statistics()
            context['team_stats'] = team_stats
            
            # Статистика по проектам
            project_stats = FileSystemAdminHelpers.get_project_file_statistics()
            context['project_stats'] = project_stats
            
            # Топ файлов по размеру
            large_files = FileSystemAdminHelpers.get_large_files()
            context['large_files'] = large_files
            
        except Exception as e:
            messages.error(request, f'Ошибка получения статистики: {e}')
            context['error'] = str(e)
        
        return render(request, 'admin/utils/file_statistics.html', context)
    
    @staff_member_required
    def file_diagnostics_view(self, request):
        """Представление для диагностики проблем с файлами"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        context = {
            'title': 'Диагностика файловой системы',
            'has_permission': True,
        }
        
        try:
            # Проверка целостности структуры
            integrity_report = FileSystemAdminHelpers.check_structure_integrity()
            context['integrity_report'] = integrity_report
            
            # Поиск осиротевших файлов
            orphaned_files = FileSystemAdminHelpers.find_orphaned_files()
            context['orphaned_files'] = orphaned_files
            
            # Проверка прав доступа
            permission_issues = FileSystemAdminHelpers.check_file_permissions()
            context['permission_issues'] = permission_issues
            
            # Проверка дублирующихся файлов
            duplicate_files = FileSystemAdminHelpers.find_duplicate_files()
            context['duplicate_files'] = duplicate_files
            
        except Exception as e:
            messages.error(request, f'Ошибка диагностики: {e}')
            context['error'] = str(e)
        
        return render(request, 'admin/utils/file_diagnostics.html', context)
    
    @staff_member_required
    def file_management_view(self, request):
        """Представление для управления файлами"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        context = {
            'title': 'Управление файлами',
            'has_permission': True,
        }
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            try:
                if action == 'cleanup_orphaned':
                    result = FileSystemAdminHelpers.cleanup_orphaned_files(request.POST.get('dry_run') == 'on')
                    messages.success(request, f'Очистка завершена: удалено {result["files_deleted"]} файлов')
                
                elif action == 'fix_permissions':
                    result = FileSystemAdminHelpers.fix_file_permissions()
                    messages.success(request, f'Права доступа исправлены: {result["files_fixed"]} файлов, {result["directories_fixed"]} папок')
                
                elif action == 'validate_structure':
                    result = FileSystemAdminHelpers.validate_and_fix_structure()
                    messages.success(request, f'Структура проверена: создано {result["directories_created"]} папок')
                
                elif action == 'create_missing_dirs':
                    result = FileSystemAdminHelpers.create_missing_directories()
                    messages.success(request, f'Созданы недостающие папки: {result["directories_created"]}')
                
                else:
                    messages.error(request, 'Неизвестное действие')
                    
            except Exception as e:
                messages.error(request, f'Ошибка выполнения действия: {e}')
        
        # Получаем доступные действия
        available_actions = FileSystemAdminHelpers.get_available_management_actions()
        context['available_actions'] = available_actions
        
        return render(request, 'admin/utils/file_management.html', context)
    
    @staff_member_required
    def api_file_tree(self, request):
        """API для получения дерева файлов"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        try:
            path = request.GET.get('path', '')
            tree = FileSystemAdminHelpers.build_file_tree(path)
            return JsonResponse(tree, json_dumps_params={'ensure_ascii': False, 'default': str})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staff_member_required
    @csrf_exempt
    def api_cleanup_orphaned(self, request):
        """API для очистки осиротевших файлов"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method allowed'}, status=405)
        
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            dry_run = data.get('dry_run', True)
            result = FileSystemAdminHelpers.cleanup_orphaned_files(dry_run)
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'default': str})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staff_member_required
    @csrf_exempt
    def api_fix_permissions(self, request):
        """API для исправления прав доступа"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method allowed'}, status=405)
        
        try:
            result = FileSystemAdminHelpers.fix_file_permissions()
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'default': str})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @staff_member_required
    @csrf_exempt
    def api_validate_structure(self, request):
        """API для валидации структуры"""
        from utils.admin_helpers import FileSystemAdminHelpers
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method allowed'}, status=405)
        
        try:
            result = FileSystemAdminHelpers.validate_and_fix_structure()
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'default': str})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Создаем экземпляр административного интерфейса
file_system_admin = FileSystemAdminView()


class FileSystemStatusAdmin(admin.ModelAdmin):
    """Фиктивная модель для отображения статуса файловой системы в админке"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Переопределяем представление списка для показа статуса файловой системы"""
        return file_system_admin.file_system_status_view(request)


# Регистрируем URL-ы в админке
def get_admin_urls():
    """Получить дополнительные URL-ы для админки"""
    return file_system_admin.get_urls()


# Добавляем информацию о файловой системе в главную страницу админки
def admin_index_context_processor(request):
    """Контекстный процессор для добавления информации о файловой системе"""
    if request.user.is_staff:
        try:
            from utils.file_monitoring import file_metrics
            disk_usage = file_metrics.get_disk_usage()
            return {
                'file_system_disk_usage': disk_usage,
                'file_system_warning': disk_usage.get('percent_used', 0) > 80
            }
        except Exception:
            return {'file_system_error': True}
    return {}