"""
Django management команда для очистки осиротевших файлов.

Эта команда может быть запущена вручную или через cron/планировщик задач
для периодической очистки файлов, которые больше не связаны с объектами в БД.
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from utils.file_monitoring import orphaned_cleanup, file_metrics, operation_monitor


class Command(BaseCommand):
    help = 'Очистка осиротевших файлов и временных файлов'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено без фактического удаления',
        )
        
        parser.add_argument(
            '--file-types',
            nargs='+',
            choices=['user', 'team', 'project', 'image', 'temporary'],
            default=['user', 'team', 'project', 'image', 'temporary'],
            help='Типы файлов для проверки и очистки',
        )
        
        parser.add_argument(
            '--temp-file-age',
            type=int,
            default=24,
            help='Максимальный возраст временных файлов в часах (по умолчанию 24)',
        )
        
        parser.add_argument(
            '--report-only',
            action='store_true',
            help='Только показать отчет о файлах без их удаления',
        )
        
        parser.add_argument(
            '--verbose-output',
            action='store_true',
            help='Подробный вывод информации о каждом файле',
        )
        
        parser.add_argument(
            '--save-report',
            type=str,
            help='Сохранить отчет в JSON файл',
        )
    
    def handle(self, *args, **options):
        """Основная логика команды."""
        
        start_time = timezone.now()
        self.stdout.write(
            self.style.SUCCESS(f'Начало очистки осиротевших файлов: {start_time}')
        )
        
        try:
            # Настройки из аргументов
            dry_run = options['dry_run'] or options['report_only']
            file_types = options['file_types']
            temp_file_age = options['temp_file_age']
            verbose = options['verbose_output']
            
            # Показываем настройки
            self.stdout.write(f"Настройки:")
            self.stdout.write(f"  - Режим: {'Тестовый (dry-run)' if dry_run else 'Реальная очистка'}")
            self.stdout.write(f"  - Типы файлов: {', '.join(file_types)}")
            self.stdout.write(f"  - Возраст временных файлов: {temp_file_age} часов")
            self.stdout.write("")
            
            # Получаем метрики до очистки
            if verbose:
                self.stdout.write("Получение метрик файловой системы...")
                metrics_before = file_metrics.get_media_usage_breakdown()
                self._display_metrics(metrics_before, "до очистки")
            
            # Выполняем очистку
            self.stdout.write("Поиск осиротевших файлов...")
            
            # Устанавливаем возраст временных файлов
            if temp_file_age != 24:
                # Временно изменяем логику поиска временных файлов
                original_find_temp = orphaned_cleanup.find_temporary_files
                orphaned_cleanup.find_temporary_files = lambda: original_find_temp(temp_file_age)
            
            # Выполняем очистку
            cleanup_result = orphaned_cleanup.cleanup_orphaned_files(
                dry_run=dry_run,
                file_types=file_types
            )
            
            # Восстанавливаем оригинальный метод
            if temp_file_age != 24:
                orphaned_cleanup.find_temporary_files = original_find_temp
            
            # Обрабатываем результаты
            if cleanup_result['success']:
                self._display_cleanup_results(cleanup_result, verbose)
                
                # Получаем метрики после очистки
                if verbose and not dry_run:
                    self.stdout.write("\nПолучение метрик после очистки...")
                    metrics_after = file_metrics.get_media_usage_breakdown()
                    self._display_metrics(metrics_after, "после очистки")
                    self._display_metrics_comparison(metrics_before, metrics_after)
                
                # Сохраняем отчет если требуется
                if options['save_report']:
                    self._save_report(cleanup_result, options['save_report'])
                
                # Записываем в мониторинг операций
                operation_monitor.record_operation(
                    'orphaned_file_cleanup',
                    success=True,
                    file_size=cleanup_result['statistics']['space_freed']
                )
                
            else:
                self.stdout.write(
                    self.style.ERROR(f"Ошибка при очистке: {cleanup_result.get('error', 'Неизвестная ошибка')}")
                )
                
                # Записываем ошибку в мониторинг
                operation_monitor.record_error(
                    'orphaned_file_cleanup_error',
                    cleanup_result.get('error', 'Unknown error'),
                    context={'file_types': file_types, 'dry_run': dry_run}
                )
                
                raise CommandError(f"Очистка завершилась с ошибкой: {cleanup_result.get('error')}")
            
            # Показываем время выполнения
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            self.stdout.write(
                self.style.SUCCESS(f'\nОчистка завершена за {duration:.2f} секунд')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Критическая ошибка при выполнении команды: {e}')
            )
            
            # Записываем критическую ошибку в мониторинг
            operation_monitor.record_error(
                'cleanup_command_critical_error',
                str(e),
                context={'options': options}
            )
            
            raise CommandError(f"Команда завершилась с критической ошибкой: {e}")
    
    def _display_cleanup_results(self, result, verbose=False):
        """Отобразить результаты очистки."""
        
        stats = result['statistics']
        deleted_files = result.get('deleted_files', [])
        
        self.stdout.write(f"\n{self.style.SUCCESS('=== РЕЗУЛЬТАТЫ ОЧИСТКИ ===')}")
        self.stdout.write(f"Найдено осиротевших файлов: {stats['orphaned_files_found']}")
        
        if stats['dry_run']:
            self.stdout.write(f"Файлов к удалению: {len(deleted_files)}")
            self.stdout.write(f"Места будет освобождено: {self._format_bytes(stats['space_freed'])}")
        else:
            self.stdout.write(f"Удалено файлов: {stats['files_deleted']}")
            self.stdout.write(f"Освобождено места: {self._format_bytes(stats['space_freed'])}")
        
        if stats['errors']:
            self.stdout.write(f"\n{self.style.WARNING('Ошибки:')}")
            for error in stats['errors']:
                self.stdout.write(f"  - {error}")
        
        # Подробная информация о файлах
        if verbose and deleted_files:
            self.stdout.write(f"\n{self.style.HTTP_INFO('Детали по файлам:')}")
            
            # Группируем по типам
            files_by_type = {}
            for file_info in deleted_files:
                file_type = file_info['type']
                if file_type not in files_by_type:
                    files_by_type[file_type] = []
                files_by_type[file_type].append(file_info)
            
            for file_type, files in files_by_type.items():
                self.stdout.write(f"\n  {file_type.upper()}:")
                total_size = sum(f['size'] for f in files)
                self.stdout.write(f"    Количество: {len(files)}")
                self.stdout.write(f"    Общий размер: {self._format_bytes(total_size)}")
                
                if len(files) <= 10:  # Показываем детали только для небольшого количества файлов
                    for file_info in files:
                        status = "УДАЛЕН" if file_info['deleted'] else "К УДАЛЕНИЮ"
                        self.stdout.write(
                            f"      [{status}] {file_info['path']} "
                            f"({self._format_bytes(file_info['size'])}) - {file_info['reason']}"
                        )
                else:
                    self.stdout.write(f"      ... и еще {len(files) - 10} файлов")
    
    def _display_metrics(self, metrics, label):
        """Отобразить метрики файловой системы."""
        
        self.stdout.write(f"\n{self.style.HTTP_INFO(f'=== МЕТРИКИ ФАЙЛОВОЙ СИСТЕМЫ ({label.upper()}) ===')}")
        
        if 'error' in metrics:
            self.stdout.write(f"Ошибка получения метрик: {metrics['error']}")
            return
        
        # Общая информация о диске
        disk_usage = metrics.get('disk_usage', {})
        if disk_usage and 'error' not in disk_usage:
            self.stdout.write(f"Диск:")
            self.stdout.write(f"  Общий размер: {self._format_bytes(disk_usage['total'])}")
            self.stdout.write(f"  Использовано: {self._format_bytes(disk_usage['used'])} ({disk_usage['percent_used']:.1f}%)")
            self.stdout.write(f"  Свободно: {self._format_bytes(disk_usage['free'])}")
        
        # Разбивка по категориям
        media_breakdown = metrics.get('media_breakdown', {})
        if media_breakdown:
            self.stdout.write(f"\nМедиа папки:")
            
            categories = ['users', 'teams', 'temp', 'backups', 'total']
            for category in categories:
                if category in media_breakdown and 'error' not in media_breakdown[category]:
                    info = media_breakdown[category]
                    self.stdout.write(
                        f"  {category}: {self._format_bytes(info['size_bytes'])} "
                        f"({info['file_count']} файлов)"
                    )
    
    def _display_metrics_comparison(self, before, after):
        """Отобразить сравнение метрик до и после."""
        
        self.stdout.write(f"\n{self.style.SUCCESS('=== ИЗМЕНЕНИЯ ===')}")
        
        # Сравниваем общий размер медиа папки
        before_total = before.get('media_breakdown', {}).get('total', {}).get('size_bytes', 0)
        after_total = after.get('media_breakdown', {}).get('total', {}).get('size_bytes', 0)
        
        if before_total and after_total:
            size_diff = before_total - after_total
            if size_diff > 0:
                self.stdout.write(f"Освобождено места: {self._format_bytes(size_diff)}")
            elif size_diff < 0:
                self.stdout.write(f"Добавлено файлов: {self._format_bytes(-size_diff)}")
            else:
                self.stdout.write("Размер медиа папки не изменился")
        
        # Сравниваем количество файлов
        before_files = before.get('media_breakdown', {}).get('total', {}).get('file_count', 0)
        after_files = after.get('media_breakdown', {}).get('total', {}).get('file_count', 0)
        
        if before_files and after_files:
            files_diff = before_files - after_files
            if files_diff > 0:
                self.stdout.write(f"Удалено файлов: {files_diff}")
            elif files_diff < 0:
                self.stdout.write(f"Добавлено файлов: {-files_diff}")
            else:
                self.stdout.write("Количество файлов не изменилось")
    
    def _save_report(self, cleanup_result, filename):
        """Сохранить отчет в JSON файл."""
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(cleanup_result, f, ensure_ascii=False, indent=2, default=str)
            
            self.stdout.write(f"\nОтчет сохранен в файл: {filename}")
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Не удалось сохранить отчет в {filename}: {e}")
            )
    
    def _format_bytes(self, bytes_count):
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