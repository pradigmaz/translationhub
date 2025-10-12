"""
Утилиты для оптимизации производительности приложения content
"""

from django.db import connection
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch, Count, Q
from functools import wraps
import time
import logging

logger = logging.getLogger(__name__)


def query_debugger(func):
    """
    Декоратор для отслеживания количества и времени выполнения SQL запросов
    Используется только в DEBUG режиме
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not settings.DEBUG:
            return func(*args, **kwargs)
        
        # Сбрасываем счетчик запросов
        initial_queries = len(connection.queries)
        start_time = time.time()
        
        # Выполняем функцию
        result = func(*args, **kwargs)
        
        # Подсчитываем результаты
        end_time = time.time()
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        execution_time = end_time - start_time
        
        logger.debug(
            f"Function {func.__name__}: {query_count} queries in {execution_time:.3f}s"
        )
        
        # Выводим медленные запросы
        if query_count > 10 or execution_time > 1.0:
            logger.warning(
                f"Slow function detected: {func.__name__} - "
                f"{query_count} queries, {execution_time:.3f}s"
            )
            
            # Показываем последние запросы
            recent_queries = connection.queries[initial_queries:]
            for i, query in enumerate(recent_queries[-5:], 1):
                logger.debug(f"Query {i}: {query['sql'][:200]}...")
        
        return result
    return wrapper


class ContentQueryOptimizer:
    """Класс для оптимизации запросов в приложении content"""
    
    @staticmethod
    def get_user_projects_optimized(user):
        """
        Оптимизированное получение проектов пользователя
        Использует select_related для минимизации запросов
        """
        from .models import Project
        
        return Project.objects.select_related('team').filter(
            team__members=user,
            team__teammembership__is_active=True,
            team__status='active'
        ).distinct().order_by('-updated_at')
    
    @staticmethod
    def get_user_texts_optimized(user, limit=None):
        """
        Оптимизированное получение текстов пользователя
        """
        from .models import TextContent
        
        queryset = TextContent.objects.select_related(
            'project__team', 'author'
        ).filter(
            project__team__members=user,
            project__team__teammembership__is_active=True,
            project__team__status='active',
            author=user
        ).distinct().order_by('-updated_at')
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    @staticmethod
    def get_project_texts_optimized(project, search_query=None):
        """
        Оптимизированное получение текстов проекта с поиском
        """
        from .models import TextContent
        
        queryset = TextContent.objects.select_related(
            'project__team', 'author'
        ).filter(project=project)
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) | 
                Q(content__icontains=search_query)
            )
        
        return queryset.order_by('-updated_at')
    
    @staticmethod
    def get_project_images_optimized(project):
        """
        Оптимизированное получение изображений проекта
        """
        from .models import ImageContent
        
        return ImageContent.objects.select_related(
            'project__team', 'uploader'
        ).filter(project=project).order_by('-uploaded_at')
    
    @staticmethod
    def get_dashboard_data_optimized(user):
        """
        Оптимизированное получение данных для дашборда
        Минимизирует количество запросов к БД
        """
        cache_key = f"dashboard_data_{user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Получаем все данные оптимизированными запросами
        projects = ContentQueryOptimizer.get_user_projects_optimized(user)
        recent_texts = ContentQueryOptimizer.get_user_texts_optimized(user, limit=5)
        
        # Получаем статистику одним запросом
        from .models import TextContent, ImageContent
        
        stats = {
            'total_texts': TextContent.objects.filter(
                project__team__members=user,
                project__team__teammembership__is_active=True,
                author=user
            ).count(),
            'draft_texts': TextContent.objects.filter(
                project__team__members=user,
                project__team__teammembership__is_active=True,
                author=user,
                is_draft=True
            ).count(),
            'total_images': ImageContent.objects.filter(
                project__team__members=user,
                project__team__teammembership__is_active=True,
                uploader=user
            ).count(),
        }
        
        data = {
            'projects': list(projects),
            'recent_texts': list(recent_texts),
            'stats': stats
        }
        
        # Кэшируем на 5 минут
        cache.set(cache_key, data, 300)
        
        return data


class DatabaseProfiler:
    """Класс для профилирования производительности БД"""
    
    @staticmethod
    def analyze_slow_queries(threshold_ms=100):
        """
        Анализирует медленные запросы
        """
        if not settings.DEBUG:
            logger.warning("Query analysis only available in DEBUG mode")
            return []
        
        slow_queries = []
        for query in connection.queries:
            time_ms = float(query['time']) * 1000
            if time_ms > threshold_ms:
                slow_queries.append({
                    'sql': query['sql'],
                    'time_ms': time_ms
                })
        
        return slow_queries
    
    @staticmethod
    def get_query_statistics():
        """
        Возвращает статистику по запросам
        """
        if not settings.DEBUG:
            return {'error': 'Statistics only available in DEBUG mode'}
        
        queries = connection.queries
        total_queries = len(queries)
        
        if total_queries == 0:
            return {'total_queries': 0}
        
        total_time = sum(float(q['time']) for q in queries)
        avg_time = total_time / total_queries
        
        return {
            'total_queries': total_queries,
            'total_time_ms': total_time * 1000,
            'avg_time_ms': avg_time * 1000,
            'slow_queries_count': len([
                q for q in queries 
                if float(q['time']) * 1000 > 100
            ])
        }
    
    @staticmethod
    def reset_query_log():
        """
        Сбрасывает лог запросов
        """
        if settings.DEBUG:
            connection.queries.clear()


def cache_user_projects(timeout=300):
    """
    Декоратор для кэширования проектов пользователя
    """
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            cache_key = f"user_projects_{user.id}"
            cached_result = cache.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            result = func(user, *args, **kwargs)
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator


def invalidate_user_cache(user_id):
    """
    Инвалидирует кэш пользователя при изменении данных
    """
    cache_keys = [
        f"user_projects_{user_id}",
        f"dashboard_data_{user_id}",
        f"user_texts_{user_id}",
    ]
    
    cache.delete_many(cache_keys)


# Middleware для автоматического профилирования
class QueryProfilerMiddleware:
    """
    Middleware для автоматического профилирования запросов
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)
        
        # Сбрасываем счетчик запросов
        DatabaseProfiler.reset_query_log()
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Анализируем производительность
        end_time = time.time()
        stats = DatabaseProfiler.get_query_statistics()
        
        # Логируем медленные запросы
        if stats.get('total_queries', 0) > 20 or (end_time - start_time) > 2.0:
            logger.warning(
                f"Slow request: {request.path} - "
                f"{stats.get('total_queries', 0)} queries, "
                f"{(end_time - start_time):.3f}s"
            )
            
            slow_queries = DatabaseProfiler.analyze_slow_queries()
            for query in slow_queries[:3]:  # Показываем только первые 3
                logger.warning(f"Slow query ({query['time_ms']:.1f}ms): {query['sql'][:200]}...")
        
        return response


# Утилиты для оптимизации конкретных запросов
def optimize_text_content_queries():
    """
    Применяет оптимизации к запросам TextContent
    """
    from .models import TextContent
    
    # Добавляем select_related по умолчанию
    original_get_queryset = TextContent.objects.get_queryset
    
    def optimized_get_queryset():
        return original_get_queryset().select_related('project__team', 'author')
    
    TextContent.objects.get_queryset = optimized_get_queryset


def get_content_performance_report():
    """
    Генерирует отчет о производительности приложения content
    """
    from .models import Project, TextContent, ImageContent, ContentAuditLog
    
    report = {
        'database_stats': {
            'projects_count': Project.objects.count(),
            'texts_count': TextContent.objects.count(),
            'images_count': ImageContent.objects.count(),
            'audit_logs_count': ContentAuditLog.objects.count(),
        },
        'query_stats': DatabaseProfiler.get_query_statistics(),
        'slow_queries': DatabaseProfiler.analyze_slow_queries(),
        'cache_info': {
            'cache_backend': settings.CACHES['default']['BACKEND'],
            'cache_location': settings.CACHES.get('default', {}).get('LOCATION', 'N/A'),
        }
    }
    
    return report