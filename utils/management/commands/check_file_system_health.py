"""
Django команда для проверки состояния файловой системы.

Эта команда проверяет общее состояние файловой системы TranslationHub,
включая использование диска, размеры папок и потенциальные проблемы.
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.core.mail import mail_admins
from utils.file_system import FileSystemMonitor, FileOperationLogger


class Command(BaseCommand):
    """Команда для проверки состояния файловой системы"""
    
    help = 'Check file system health and report issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--notify-admins',
            action='store_true',
            help='Send email notification to admins if issues are found',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
    
    def handle(self, *args, **options):
        """Выполнить проверку состояния файловой системы"""
        try:
            self.stdout.write("Checking file system health...")
            
            # Получаем отчет о состоянии системы
            health_report = FileSystemMonitor.check_system_health()
            
            # Выводим результаты
            if options['json']:
                self.stdout.write(json.dumps(health_report, indent=2))
            else:
                self._display_health_report(health_report, options['verbose'])
            
            # Проверяем наличие предупреждений
            warnings = health_report.get('warnings', [])
            if warnings:
                self.stdout.write(
                    self.style.WARNING(f"Found {len(warnings)} warning(s)")
                )
                
                # Отправляем уведомление администраторам если запрошено
                if options['notify_admins']:
                    self._notify_admins_about_issues(health_report)
                    self.stdout.write("Admin notification sent")
            else:
                self.stdout.write(
                    self.style.SUCCESS("File system health check passed")
                )
            
            # Логируем выполнение команды
            FileOperationLogger.log_directory_created(
                "health_check_completed",
                operation_context="management_command"
            )
            
        except Exception as e:
            FileOperationLogger.log_error("file_system_health_check", e, notify_admins=True)
            raise CommandError(f"Health check failed: {e}")
    
    def _display_health_report(self, health_report, verbose=False):
        """Отобразить отчет о состоянии системы"""
        
        # Информация о диске
        disk_usage = health_report.get('disk_usage', {})
        self.stdout.write("\n=== Disk Usage ===")
        self.stdout.write(f"Total: {self._format_bytes(disk_usage.get('total', 0))}")
        self.stdout.write(f"Used: {self._format_bytes(disk_usage.get('used', 0))}")
        self.stdout.write(f"Free: {self._format_bytes(disk_usage.get('free', 0))}")
        self.stdout.write(f"Usage: {disk_usage.get('percent_used', 0)}%")
        
        # Информация о папках
        directories = health_report.get('directories', {})
        self.stdout.write("\n=== Directory Information ===")
        
        for dir_name, dir_info in directories.items():
            self.stdout.write(f"\n{dir_name.upper()}:")
            self.stdout.write(f"  Exists: {dir_info.get('exists', False)}")
            self.stdout.write(f"  Size: {self._format_bytes(dir_info.get('size', 0))}")
            
            if verbose:
                file_count = dir_info.get('file_count', {})
                self.stdout.write(f"  Files: {file_count.get('files', 0)}")
                self.stdout.write(f"  Directories: {file_count.get('directories', 0)}")
        
        # Предупреждения
        warnings = health_report.get('warnings', [])
        if warnings:
            self.stdout.write("\n=== Warnings ===")
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"⚠ {warning}"))
        
        # Ошибки
        if 'error' in health_report:
            self.stdout.write("\n=== Errors ===")
            self.stdout.write(self.style.ERROR(f"✗ {health_report['error']}"))
    
    def _format_bytes(self, bytes_value):
        """Форматировать размер в байтах в читаемый вид"""
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(bytes_value)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.1f} {units[unit_index]}"
    
    def _notify_admins_about_issues(self, health_report):
        """Отправить уведомление администраторам о проблемах"""
        try:
            warnings = health_report.get('warnings', [])
            if not warnings:
                return
            
            subject = "[TranslationHub] File System Health Check - Issues Found"
            
            message = f"""
File System Health Check Report
==============================

Timestamp: {health_report.get('timestamp', 'Unknown')}

WARNINGS FOUND:
{chr(10).join(f"• {warning}" for warning in warnings)}

DISK USAGE:
• Total: {self._format_bytes(health_report.get('disk_usage', {}).get('total', 0))}
• Used: {self._format_bytes(health_report.get('disk_usage', {}).get('used', 0))}
• Free: {self._format_bytes(health_report.get('disk_usage', {}).get('free', 0))}
• Usage: {health_report.get('disk_usage', {}).get('percent_used', 0)}%

Please review the file system status and take appropriate action.

Full report (JSON):
{json.dumps(health_report, indent=2)}
            """
            
            mail_admins(subject, message, fail_silently=True)
            
        except Exception as e:
            FileOperationLogger.log_error("notify_admins_health_check", e)