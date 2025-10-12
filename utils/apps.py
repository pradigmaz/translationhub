"""
Конфигурация приложения utils для управления файловой структурой.
"""

from django.apps import AppConfig


class UtilsConfig(AppConfig):
    """Конфигурация приложения utils"""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utils'
    verbose_name = 'Утилиты'
    
    def ready(self):
        """
        Инициализация приложения.
        
        Импортирует сигналы и создает базовые папки при запуске системы.
        Инициализирует систему мониторинга файлов.
        """
        # Импортируем сигналы для их регистрации
        from . import signals
        
        # Инициализируем базовые папки
        try:
            signals.initialize_base_directories()
        except Exception as e:
            # Логируем ошибку, но не прерываем запуск приложения
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to initialize base directories: {e}")
        
        # Инициализируем систему мониторинга файлов
        try:
            from .file_monitoring import file_metrics, operation_monitor
            # Инициализируем кэш метрик
            file_metrics.get_cached_metrics()
            
            import logging
            monitoring_logger = logging.getLogger('file_monitoring')
            monitoring_logger.info("File monitoring system initialized successfully")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to initialize file monitoring system: {e}")