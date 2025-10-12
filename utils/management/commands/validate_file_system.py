"""
Django команда для валидации файловой системы и проверки соответствия ограничениям.

Эта команда проверяет существующие файлы в системе на соответствие
текущим правилам валидации и ограничениям.
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from pathlib import Path
from typing import Dict, List, Any
import os

from utils.file_system import (
    FileValidationSystem, FilePathManager, FileOperationLogger,
    FileValidationError, FilePathValidator
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Валидация файловой системы и проверка соответствия ограничениям'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Автоматически исправить найденные проблемы (где возможно)',
        )
        parser.add_argument(
            '--check-permissions',
            action='store_true',
            help='Проверить права доступа к файлам',
        )
        parser.add_argument(
            '--check-sizes',
            action='store_true',
            help='Проверить размеры файлов на соответствие ограничениям',
        )
        parser.add_argument(
            '--check-names',
            action='store_true',
            help='Проверить имена файлов на соответствие правилам',
        )
        parser.add_argument(
            '--check-orphans',
            action='store_true',
            help='Найти файлы-сироты (без связанных объектов в БД)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Проверить файлы только для указанного пользователя',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод информации',
        )
    
    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.fix_issues = options.get('fix', False)
        
        self.stdout.write(
            self.style.SUCCESS('Начинаем валидацию файловой системы...')
        )
        
        validation_results = {
            'total_files_checked': 0,
            'issues_found': 0,
            'issues_fixed': 0,
            'errors': [],
            'warnings': [],
            'summary': {}
        }
        
        try:
            # Проверяем различные аспекты файловой системы
            if options.get('check_permissions') or not any([
                options.get('check_sizes'),
                options.get('check_names'),
                options.get('check_orphans')
            ]):
                self._check_file_permissions(validation_results, options)
            
            if options.get('check_sizes') or not any([
                options.get('check_permissions'),
                options.get('check_names'),
                options.get('check_orphans')
            ]):
                self._check_file_sizes(validation_results, options)
            
            if options.get('check_names') or not any([
                options.get('check_permissions'),
                options.get('check_sizes'),
                options.get('check_orphans')
            ]):
                self._check_file_names(validation_results, options)
            
            if options.get('check_orphans') or not any([
                options.get('check_permissions'),
                options.get('check_sizes'),
                options.get('check_names')
            ]):
                self._check_orphaned_files(validation_results, options)
            
            # Выводим результаты
            self._print_validation_results(validation_results)
            
        except Exception as e:
            raise CommandError(f'Ошибка при валидации файловой системы: {e}')
    
    def _check_file_permissions(self, results: Dict[str, Any], options: Dict[str, Any]):
        """Проверить права доступа к файлам."""
        self.stdout.write('Проверяем права доступа к файлам...')
        
        media_root = Path(FilePathManager.get_user_path(1).parent.parent)  # media/
        
        permission_issues = []
        files_checked = 0
        
        for file_path in media_root.rglob('*'):
            if file_path.is_file():
                files_checked += 1
                
                # Проверяем права на чтение и запись
                if not os.access(file_path, os.R_OK):
                    permission_issues.append({
                        'file': str(file_path),
                        'issue': 'Нет прав на чтение',
                        'severity': 'error'
                    })
                
                if not os.access(file_path, os.W_OK):
                    permission_issues.append({
                        'file': str(file_path),
                        'issue': 'Нет прав на запись',
                        'severity': 'warning'
                    })
        
        results['total_files_checked'] += files_checked
        results['issues_found'] += len(permission_issues)
        results['summary']['permission_issues'] = len(permission_issues)
        
        if permission_issues:
            self.stdout.write(
                self.style.WARNING(f'Найдено {len(permission_issues)} проблем с правами доступа')
            )
            
            if self.verbose:
                for issue in permission_issues[:10]:  # Показываем первые 10
                    self.stdout.write(f"  - {issue['file']}: {issue['issue']}")
                
                if len(permission_issues) > 10:
                    self.stdout.write(f"  ... и еще {len(permission_issues) - 10} проблем")
        else:
            self.stdout.write(self.style.SUCCESS('Проблем с правами доступа не найдено'))
    
    def _check_file_sizes(self, results: Dict[str, Any], options: Dict[str, Any]):
        """Проверить размеры файлов на соответствие ограничениям."""
        self.stdout.write('Проверяем размеры файлов...')
        
        size_issues = []
        files_checked = 0
        
        # Проверяем аватарки пользователей
        for user in User.objects.filter(avatar__isnull=False):
            if user.avatar:
                avatar_path = Path(user.avatar.path) if hasattr(user.avatar, 'path') else None
                if avatar_path and avatar_path.exists():
                    files_checked += 1
                    file_size = avatar_path.stat().st_size
                    max_size = FileValidationSystem.FILE_TYPE_CONFIGS['avatar']['max_size']
                    
                    if file_size > max_size:
                        size_issues.append({
                            'file': str(avatar_path),
                            'type': 'avatar',
                            'size': file_size,
                            'max_size': max_size,
                            'user_id': user.id,
                            'severity': 'error'
                        })
        
        # Проверяем изображения проектов
        try:
            from content.models import ImageContent
            
            for image in ImageContent.objects.all():
                if image.image:
                    image_path = Path(image.image.path) if hasattr(image.image, 'path') else None
                    if image_path and image_path.exists():
                        files_checked += 1
                        file_size = image_path.stat().st_size
                        max_size = FileValidationSystem.FILE_TYPE_CONFIGS['project_image']['max_size']
                        
                        if file_size > max_size:
                            size_issues.append({
                                'file': str(image_path),
                                'type': 'project_image',
                                'size': file_size,
                                'max_size': max_size,
                                'severity': 'error'
                            })
        except ImportError:
            self.stdout.write(self.style.WARNING('Модель ImageContent не найдена, пропускаем проверку изображений проектов'))
        
        results['total_files_checked'] += files_checked
        results['issues_found'] += len(size_issues)
        results['summary']['size_issues'] = len(size_issues)
        
        if size_issues:
            self.stdout.write(
                self.style.WARNING(f'Найдено {len(size_issues)} файлов с превышением размера')
            )
            
            if self.verbose:
                for issue in size_issues[:10]:
                    size_mb = issue['size'] / (1024 * 1024)
                    max_size_mb = issue['max_size'] / (1024 * 1024)
                    self.stdout.write(
                        f"  - {issue['file']}: {size_mb:.1f} МБ (лимит: {max_size_mb:.1f} МБ)"
                    )
                
                if len(size_issues) > 10:
                    self.stdout.write(f"  ... и еще {len(size_issues) - 10} файлов")
        else:
            self.stdout.write(self.style.SUCCESS('Файлов с превышением размера не найдено'))
    
    def _check_file_names(self, results: Dict[str, Any], options: Dict[str, Any]):
        """Проверить имена файлов на соответствие правилам."""
        self.stdout.write('Проверяем имена файлов...')
        
        name_issues = []
        files_checked = 0
        fixed_count = 0
        
        media_root = Path(FilePathManager.get_user_path(1).parent.parent)  # media/
        
        for file_path in media_root.rglob('*'):
            if file_path.is_file():
                files_checked += 1
                filename = file_path.name
                
                # Проверяем базовую валидность имени
                if not FilePathValidator.validate_filename(filename):
                    issue = {
                        'file': str(file_path),
                        'issue': 'Недопустимые символы в имени файла',
                        'severity': 'error',
                        'fixable': True
                    }
                    name_issues.append(issue)
                    
                    # Пытаемся исправить если включен режим исправления
                    if self.fix_issues:
                        try:
                            clean_name = FilePathValidator.sanitize_filename_advanced(filename)
                            new_path = file_path.parent / clean_name
                            
                            if not new_path.exists():
                                file_path.rename(new_path)
                                fixed_count += 1
                                issue['fixed'] = True
                                
                                FileOperationLogger.log_file_uploaded(
                                    str(new_path), None, file_path.stat().st_size,
                                    'unknown', 'filename_fixed_by_validation'
                                )
                        except Exception as e:
                            issue['fix_error'] = str(e)
                
                # Проверяем безопасность имени
                elif not FilePathValidator.validate_filename_security(filename):
                    name_issues.append({
                        'file': str(file_path),
                        'issue': 'Небезопасное имя файла',
                        'severity': 'warning',
                        'fixable': False
                    })
        
        results['total_files_checked'] += files_checked
        results['issues_found'] += len(name_issues)
        results['issues_fixed'] += fixed_count
        results['summary']['name_issues'] = len(name_issues)
        results['summary']['names_fixed'] = fixed_count
        
        if name_issues:
            self.stdout.write(
                self.style.WARNING(f'Найдено {len(name_issues)} проблем с именами файлов')
            )
            
            if fixed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Исправлено {fixed_count} имен файлов')
                )
            
            if self.verbose:
                for issue in name_issues[:10]:
                    status = " (исправлено)" if issue.get('fixed') else ""
                    self.stdout.write(f"  - {issue['file']}: {issue['issue']}{status}")
                
                if len(name_issues) > 10:
                    self.stdout.write(f"  ... и еще {len(name_issues) - 10} проблем")
        else:
            self.stdout.write(self.style.SUCCESS('Проблем с именами файлов не найдено'))
    
    def _check_orphaned_files(self, results: Dict[str, Any], options: Dict[str, Any]):
        """Найти файлы-сироты без связанных объектов в БД."""
        self.stdout.write('Ищем файлы-сироты...')
        
        orphaned_files = []
        files_checked = 0
        removed_count = 0
        
        # Получаем все файлы из БД
        db_files = set()
        
        # Аватарки пользователей
        for user in User.objects.filter(avatar__isnull=False):
            if user.avatar:
                db_files.add(str(user.avatar))
        
        # Изображения проектов
        try:
            from content.models import ImageContent
            
            for image in ImageContent.objects.all():
                if image.image:
                    db_files.add(str(image.image))
        except ImportError:
            pass
        
        # Проверяем файлы в файловой системе
        media_root = Path(FilePathManager.get_user_path(1).parent.parent)  # media/
        
        for file_path in media_root.rglob('*'):
            if file_path.is_file():
                files_checked += 1
                
                # Получаем относительный путь от media/
                try:
                    relative_path = str(file_path.relative_to(media_root))
                    
                    if relative_path not in db_files:
                        # Исключаем системные файлы
                        if not any(relative_path.startswith(prefix) for prefix in [
                            'temp/', '.', 'staticfiles/', 'admin/'
                        ]):
                            orphan = {
                                'file': str(file_path),
                                'relative_path': relative_path,
                                'size': file_path.stat().st_size,
                                'severity': 'warning'
                            }
                            orphaned_files.append(orphan)
                            
                            # Удаляем если включен режим исправления
                            if self.fix_issues:
                                try:
                                    file_path.unlink()
                                    removed_count += 1
                                    orphan['removed'] = True
                                    
                                    FileOperationLogger.log_file_deleted(
                                        str(file_path), None, 'orphan_cleanup_by_validation'
                                    )
                                except Exception as e:
                                    orphan['remove_error'] = str(e)
                
                except ValueError:
                    # Файл не в media папке
                    continue
        
        results['total_files_checked'] += files_checked
        results['issues_found'] += len(orphaned_files)
        results['issues_fixed'] += removed_count
        results['summary']['orphaned_files'] = len(orphaned_files)
        results['summary']['orphans_removed'] = removed_count
        
        if orphaned_files:
            total_size = sum(f['size'] for f in orphaned_files)
            size_mb = total_size / (1024 * 1024)
            
            self.stdout.write(
                self.style.WARNING(
                    f'Найдено {len(orphaned_files)} файлов-сирот '
                    f'общим размером {size_mb:.1f} МБ'
                )
            )
            
            if removed_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Удалено {removed_count} файлов-сирот')
                )
            
            if self.verbose:
                for orphan in orphaned_files[:10]:
                    size_kb = orphan['size'] / 1024
                    status = " (удален)" if orphan.get('removed') else ""
                    self.stdout.write(f"  - {orphan['relative_path']}: {size_kb:.1f} КБ{status}")
                
                if len(orphaned_files) > 10:
                    self.stdout.write(f"  ... и еще {len(orphaned_files) - 10} файлов")
        else:
            self.stdout.write(self.style.SUCCESS('Файлов-сирот не найдено'))
    
    def _print_validation_results(self, results: Dict[str, Any]):
        """Вывести итоговые результаты валидации."""
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('ИТОГИ ВАЛИДАЦИИ ФАЙЛОВОЙ СИСТЕМЫ'))
        self.stdout.write('='*50)
        
        self.stdout.write(f"Проверено файлов: {results['total_files_checked']}")
        self.stdout.write(f"Найдено проблем: {results['issues_found']}")
        
        if self.fix_issues:
            self.stdout.write(f"Исправлено проблем: {results['issues_fixed']}")
        
        # Детальная статистика
        summary = results['summary']
        if summary:
            self.stdout.write('\nДетальная статистика:')
            
            if 'permission_issues' in summary:
                self.stdout.write(f"  - Проблемы с правами доступа: {summary['permission_issues']}")
            
            if 'size_issues' in summary:
                self.stdout.write(f"  - Файлы с превышением размера: {summary['size_issues']}")
            
            if 'name_issues' in summary:
                self.stdout.write(f"  - Проблемы с именами файлов: {summary['name_issues']}")
                if 'names_fixed' in summary:
                    self.stdout.write(f"    (исправлено: {summary['names_fixed']})")
            
            if 'orphaned_files' in summary:
                self.stdout.write(f"  - Файлы-сироты: {summary['orphaned_files']}")
                if 'orphans_removed' in summary:
                    self.stdout.write(f"    (удалено: {summary['orphans_removed']})")
        
        # Рекомендации
        if results['issues_found'] > 0:
            self.stdout.write('\nРекомендации:')
            
            if not self.fix_issues:
                self.stdout.write('  - Запустите команду с флагом --fix для автоматического исправления проблем')
            
            if results['issues_found'] > results['issues_fixed']:
                self.stdout.write('  - Некоторые проблемы требуют ручного вмешательства')
                self.stdout.write('  - Проверьте логи для получения дополнительной информации')
        
        self.stdout.write('\n' + self.style.SUCCESS('Валидация завершена!'))