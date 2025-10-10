"""
Middleware для дополнительной безопасности TranslationHub
"""

import logging
from django.http import HttpResponseForbidden
from django.core.exceptions import SuspiciousOperation
from django.utils.deprecation import MiddlewareMixin

security_logger = logging.getLogger('security')


class SecurityMiddleware(MiddlewareMixin):
    """
    Middleware для логирования подозрительной активности и дополнительной защиты
    """
    
    def process_request(self, request):
        """Обработка входящих запросов"""
        
        # Получение IP адреса клиента
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Логирование подозрительных запросов
        suspicious_patterns = [
            'admin', 'wp-admin', 'phpmyadmin', '.php', '.asp', '.jsp',
            'eval(', 'script>', '<script', 'javascript:', 'vbscript:',
            'union select', 'drop table', 'insert into', 'delete from'
        ]
        
        path = request.path.lower()
        query = request.GET.urlencode().lower()
        
        for pattern in suspicious_patterns:
            if pattern in path or pattern in query:
                security_logger.warning(
                    f"Suspicious request detected from IP {ip}: "
                    f"Path: {request.path}, Query: {request.GET.urlencode()}, "
                    f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}"
                )
                break
        
        # Проверка на слишком длинные URL (возможная атака)
        if len(request.path) > 2000:
            security_logger.error(f"Extremely long URL from IP {ip}: {len(request.path)} characters")
            raise SuspiciousOperation("URL too long")
        
        return None
    
    def process_exception(self, request, exception):
        """Логирование исключений для анализа безопасности"""
        if isinstance(exception, SuspiciousOperation):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
                
            security_logger.error(
                f"SuspiciousOperation from IP {ip}: {str(exception)}, "
                f"Path: {request.path}, User: {getattr(request, 'user', 'Anonymous')}"
            )
        
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """
    Простой middleware для ограничения частоты запросов
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_counts = {}  # В продакшене используйте Redis или Memcached
        super().__init__(get_response)
    
    def process_request(self, request):
        """Проверка лимита запросов"""
        
        # Получение IP адреса
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Простая проверка лимита (в продакшене нужна более сложная логика)
        import time
        current_time = int(time.time())
        minute_key = f"{ip}:{current_time // 60}"
        
        if minute_key not in self.request_counts:
            self.request_counts[minute_key] = 0
        
        self.request_counts[minute_key] += 1
        
        # Лимит: 100 запросов в минуту с одного IP
        if self.request_counts[minute_key] > 100:
            security_logger.warning(f"Rate limit exceeded for IP {ip}: {self.request_counts[minute_key]} requests/minute")
            return HttpResponseForbidden("Rate limit exceeded")
        
        # Очистка старых записей (простая реализация)
        keys_to_remove = [key for key in self.request_counts.keys() 
                         if int(key.split(':')[1]) < current_time // 60 - 5]
        for key in keys_to_remove:
            del self.request_counts[key]
        
        return None