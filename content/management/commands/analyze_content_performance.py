"""
Management команда для анализа производительности приложения content
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from content.models import Project, TextContent, ImageContent, ContentAuditLog
from content.performance import DatabaseProfiler, get_content_performance_report
import json


class Command(BaseCommand):
    help = 'Анализирует производительность приложения content и предлагает оптимизации'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Показать детальный анализ с примерами запросов',
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Экспортировать отчет в JSON файл',
        )
        parser.add_argument(
            '--check-indexes',
            action='store_true',
            help='Проверить эффективность индексов',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 Анализ производительности приложения content')
        )
        
        # Получаем общий отчет
        report = get_content_performance_report()
        
        # Выводим статистику БД
        self.show_database_stats(report['database_stats'])
        
        # Анализируем запросы
        if settings.DEBUG:
            self.analyze_queries(report['query_stats'], options['detailed'])
        else:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  Анализ запросов доступен только в DEBUG режиме'
                )
            )
        
        # Проверяем индексы
        if options['check_indexes']:
            self.check_database_indexes()
        
        # Предлагаем оптимизации
        self.suggest_optimizations(report)
        
        # Экспортируем отчет
        if options['export']:
            self.export_report(report, options['export'])

    def show_database_stats(self, stats):
        """Показывает статистику базы данных"""
        self.stdout.write('\n📊 Статистика базы данных:')
        self.stdout.write(f"  • Проекты: {stats['projects_count']}")
        self.stdout.write(f"  • Тексты: {stats['texts_count']}")
        self.stdout.write(f"  • Изображения: {stats['images_count']}")
        self.stdout.write(f"  • Логи аудита: {stats['audit_logs_count']}")

    def analyze_queries(self, query_stats, detailed=False):
        """Анализирует производительность запросов"""
        self.stdout.write('\n🚀 Анализ запросов:')
        
        if query_stats.get('error'):
            self.stdout.write(
                self.style.WARNING(f"  ⚠️  {query_stats['error']}")
            )
            return
        
        total_queries = query_stats.get('total_queries', 0)
        if total_queries == 0:
            self.stdout.write('  • Запросы не выполнялись')
            return
        
        self.stdout.write(f"  • Всего запросов: {total_queries}")
        self.stdout.write(f"  • Общее время: {query_stats.get('total_time_ms', 0):.1f}ms")
        self.stdout.write(f"  • Среднее время: {query_stats.get('avg_time_ms', 0):.1f}ms")
        self.stdout.write(f"  • Медленных запросов: {query_stats.get('slow_queries_count', 0)}")
        
        if detailed:
            slow_queries = DatabaseProfiler.analyze_slow_queries()
            if slow_queries:
                self.stdout.write('\n🐌 Медленные запросы:')
                for i, query in enumerate(slow_queries[:5], 1):
                    self.stdout.write(f"  {i}. {query['time_ms']:.1f}ms: {query['sql'][:100]}...")

    def check_database_indexes(self):
        """Проверяет эффективность индексов"""
        self.stdout.write('\n🔍 Проверка индексов:')
        
        with connection.cursor() as cursor:
            # Проверяем индексы для SQLite
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                cursor.execute("""
                    SELECT name, sql FROM sqlite_master 
                    WHERE type='index' AND name LIKE 'content_%'
                    ORDER BY name
                """)
                indexes = cursor.fetchall()
                
                if indexes:
                    self.stdout.write('  ✅ Найденные индексы:')
                    for name, sql in indexes:
                        self.stdout.write(f"    • {name}")
                else:
                    self.stdout.write('  ❌ Индексы не найдены')
            else:
                self.stdout.write('  ℹ️  Проверка индексов поддерживается только для SQLite')

    def suggest_optimizations(self, report):
        """Предлагает оптимизации"""
        self.stdout.write('\n💡 Рекомендации по оптимизации:')
        
        stats = report['database_stats']
        
        # Рекомендации по количеству записей
        if stats['texts_count'] > 1000:
            self.stdout.write('  📝 Большое количество текстов:')
            self.stdout.write('    • Рассмотрите архивирование старых текстов')
            self.stdout.write('    • Увеличьте размер страницы в пагинации')
        
        if stats['audit_logs_count'] > 10000:
            self.stdout.write('  📋 Большое количество логов аудита:')
            self.stdout.write('    • Настройте автоматическую очистку старых логов')
            self.stdout.write('    • Рассмотрите партиционирование таблицы логов')
        
        # Рекомендации по кэшированию
        cache_backend = report.get('cache_info', {}).get('cache_backend', '')
        if 'dummy' in cache_backend.lower():
            self.stdout.write('  🚨 Кэширование отключено:')
            self.stdout.write('    • Настройте Redis или Memcached для продакшена')
            self.stdout.write('    • Включите кэширование дашборда и проектов')
        
        # Рекомендации по запросам
        query_stats = report.get('query_stats', {})
        slow_queries_count = query_stats.get('slow_queries_count', 0)
        if slow_queries_count > 0:
            self.stdout.write(f'  🐌 Обнаружено {slow_queries_count} медленных запросов:')
            self.stdout.write('    • Проверьте использование select_related и prefetch_related')
            self.stdout.write('    • Добавьте индексы для часто используемых полей')
            self.stdout.write('    • Оптимизируйте сложные фильтры')

    def export_report(self, report, filename):
        """Экспортирует отчет в JSON файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Отчет экспортирован в {filename}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Ошибка экспорта: {e}')
            )

    def style_performance_level(self, level):
        """Возвращает стилизованный уровень производительности"""
        if level == 'excellent':
            return self.style.SUCCESS('Отлично')
        elif level == 'good':
            return self.style.SUCCESS('Хорошо')
        elif level == 'average':
            return self.style.WARNING('Средне')
        elif level == 'poor':
            return self.style.ERROR('Плохо')
        else:
            return level