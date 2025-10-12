"""
Административный интерфейс для мониторинга файловой системы.

Предоставляет веб-интерфейс для просмотра метрик файловой системы,
статистики операций и управления очисткой осиротевших файлов.
"""

from django.contrib import admin
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils.html import format_html
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.utils import timezone
import json

from .file_monitoring import file_metrics, operation_monitor, orphaned_cleanup


class FileMonitoringAdmin:
    """
    Административный класс для мониторинга файловой системы.
    
    Предоставляет интерфейс для просмотра метрик и управления файлами.
    """
    
    def get_urls(self):
        """Получить URL-ы для административного интерфейса."""
        urls = [
            path('file-metrics/', self.admin_site.admin_view(self.file_metrics_view), name='file_metrics'),
            path('operation-stats/', self.admin_site.admin_view(self.operation_stats_view), name='operation_stats'),
            path('cleanup-orphaned/', self.admin_site.admin_view(self.cleanup_orphaned_view), name='cleanup_orphaned'),
            path('api/metrics/', self.admin_site.admin_view(self.api_metrics), name='api_metrics'),
            path('api/cleanup/', self.admin_site.admin_view(self.api_cleanup), name='api_cleanup'),
        ]
        return urls
    
    @method_decorator(staff_member_required)
    def file_metrics_view(self, request):
        """Представление для отображения метрик файловой системы."""
        
        context = {
            'title': 'Метрики файловой системы',
            'has_permission': True,
        }
        
        try:
            # Получаем метрики
            metrics = file_metrics.get_cached_metrics()
            context['metrics'] = metrics
            context['metrics_json'] = json.dumps(metrics, default=str, ensure_ascii=False)
            
            # Проверяем критические состояния
            disk_usage = metrics.get('disk_usage', {})
            if disk_usage and disk_usage.get('percent_used', 0) > 90:
                messages.error(request, 'Критически мало места на диске!')
            elif disk_usage and disk_usage.get('percent_used', 0) > 80:
                messages.warning(request, 'Мало места на диске')
            
        except Exception as e:
            messages.error(request, f'Ошибка получения метрик: {e}')
            context['error'] = str(e)
        
        return render(request, 'admin/utils/file_metrics.html', context)
    
    @method_decorator(staff_member_required)
    def operation_stats_view(self, request):
        """Представление для отображения статистики операций."""
        
        context = {
            'title': 'Статистика файловых операций',
            'has_permission': True,
        }
        
        try:
            # Получаем статистику операций
            stats = operation_monitor.get_operation_statistics()
            context['stats'] = stats
            context['stats_json'] = json.dumps(stats, default=str, ensure_ascii=False)
            
            # Проверяем на высокий уровень ошибок
            total_operations = sum(op.get('total_count', 0) for op in stats.get('operations', {}).values())
            total_errors = sum(op.get('error_count', 0) for op in stats.get('operations', {}).values())
            
            if total_operations > 0:
                error_rate = (total_errors / total_operations) * 100
                if error_rate > 10:
                    messages.error(request, f'Высокий уровень ошибок: {error_rate:.1f}%')
                elif error_rate > 5:
                    messages.warning(request, f'Повышенный уровень ошибок: {error_rate:.1f}%')
            
        except Exception as e:
            messages.error(request, f'Ошибка получения статистики: {e}')
            context['error'] = str(e)
        
        return render(request, 'admin/utils/operation_stats.html', context)
    
    @method_decorator(staff_member_required)
    def cleanup_orphaned_view(self, request):
        """Представление для управления очисткой осиротевших файлов."""
        
        context = {
            'title': 'Очистка осиротевших файлов',
            'has_permission': True,
        }
        
        if request.method == 'POST':
            try:
                # Получаем параметры из формы
                dry_run = request.POST.get('dry_run') == 'on'
                file_types = request.POST.getlist('file_types')
                
                if not file_types:
                    file_types = ['user', 'team', 'project', 'image', 'temporary']
                
                # Выполняем очистку
                result = orphaned_cleanup.cleanup_orphaned_files(
                    dry_run=dry_run,
                    file_types=file_types
                )
                
                context['cleanup_result'] = result
                
                if result['success']:
                    if dry_run:
                        messages.info(request, f'Найдено {result["statistics"]["orphaned_files_found"]} осиротевших файлов')
                    else:
                        messages.success(request, f'Удалено {result["statistics"]["files_deleted"]} файлов')
                else:
                    messages.error(request, f'Ошибка очистки: {result.get("error")}')
                
            except Exception as e:
                messages.error(request, f'Ошибка выполнения очистки: {e}')
                context['error'] = str(e)
        
        return render(request, 'admin/utils/cleanup_orphaned.html', context)
    
    @method_decorator(staff_member_required)
    def api_metrics(self, request):
        """API для получения метрик в JSON формате."""
        
        try:
            metrics = file_metrics.get_cached_metrics()
            return JsonResponse(metrics, json_dumps_params={'ensure_ascii': False, 'default': str})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @method_decorator(staff_member_required)
    @method_decorator(csrf_exempt)
    def api_cleanup(self, request):
        """API для выполнения очистки осиротевших файлов."""
        
        if request.method != 'POST':
            return JsonResponse({'error': 'Only POST method allowed'}, status=405)
        
        try:
            # Получаем параметры из JSON или POST данных
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            dry_run = data.get('dry_run', True)
            file_types = data.get('file_types', ['user', 'team', 'project', 'image', 'temporary'])
            
            # Выполняем очистку
            result = orphaned_cleanup.cleanup_orphaned_files(
                dry_run=dry_run,
                file_types=file_types
            )
            
            return JsonResponse(result, json_dumps_params={'ensure_ascii': False, 'default': str})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Создаем экземпляр для использования в URL-ах
file_monitoring_admin = FileMonitoringAdmin()


def format_bytes(bytes_count):
    """Форматировать размер в байтах в читаемый вид."""
    if bytes_count == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(bytes_count)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


# Регистрируем фильтр для шаблонов
from django import template
register = template.Library()

@register.filter
def format_file_size(bytes_count):
    """Шаблонный фильтр для форматирования размера файлов."""
    return format_bytes(bytes_count)

@register.filter
def percentage(value, total):
    """Шаблонный фильтр для вычисления процентов."""
    if not total or total == 0:
        return 0
    return round((value / total) * 100, 1)