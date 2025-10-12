"""
Система мониторинга файлов для TranslationHub.

Этот модуль содержит классы для мониторинга файловых операций,
отслеживания использования дискового пространства и очистки осиротевших файлов.
"""

import os
import shutil
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone
from django.db import models
from django.contrib.auth import get_user_model

# Модели будут импортированы лениво при необходимости
Team = None
Project = None
ImageContent = None
User = None

def _get_models():
    """Ленивый импорт моделей для избежания циклических зависимостей."""
    global Team, Project, ImageContent, User
    
    if User is None:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
        except Exception:
            User = None
    
    if Team is None:
        try:
            from teams.models import Team as TeamModel
            Team = TeamModel
        except ImportError:
            Team = None
    
    if Project is None:
        try:
            from projects.models import Project as ProjectModel
            Project = ProjectModel
        except ImportError:
            Project = None
    
    if ImageContent is None:
        try:
            from content.models import ImageContent as ImageContentModel
            ImageContent = ImageContentModel
        except ImportError:
            ImageContent = None
    
    return User, Team, Project, ImageContent

# Настройка логирования
monitoring_logger = logging.getLogger('file_monitoring')
file_logger = logging.getLogger('file_operations')


class FileSystemMetrics:
    """
    Класс для сбора и анализа метрик файловой системы.
    
    Собирает информацию об использовании дискового пространства,
    количестве файлов и их размерах по различным категориям.
    """
    
    def __init__(self):
        self.media_root = Path(settings.MEDIA_ROOT)
        self.metrics_cache = {}
        self.cache_timeout = 300  # 5 минут
        self.last_cache_update = None
    
    def get_disk_usage(self, path: Optional[Path] = None) -> Dict[str, int]:
        """
        Получить информацию об использовании дискового пространства.
        
        Args:
            path: Путь для проверки (по умолчанию MEDIA_ROOT)
            
        Returns:
            Dict[str, int]: Словарь с информацией о диске
        """
        try:
            if path is None:
                path = self.media_root
            
            if not path.exists():
                return {
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'percent_used': 0
                }
            
            # Получаем статистику диска
            disk_usage = shutil.disk_usage(path)
            
            total = disk_usage.total
            free = disk_usage.free
            used = total - free
            percent_used = (used / total * 100) if total > 0 else 0
            
            return {
                'total': total,
                'used': used,
                'free': free,
                'percent_used': round(percent_used, 2)
            }
            
        except Exception as e:
            monitoring_logger.error(f"Error getting disk usage for {path}: {e}")
            return {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent_used': 0,
                'error': str(e)
            }
    
    def get_directory_size(self, path: Path) -> Dict[str, Any]:
        """
        Получить размер директории и количество файлов.
        
        Args:
            path: Путь к директории
            
        Returns:
            Dict[str, Any]: Информация о размере и файлах
        """
        try:
            if not path.exists() or not path.is_dir():
                return {
                    'size_bytes': 0,
                    'file_count': 0,
                    'subdirectory_count': 0,
                    'error': 'Directory does not exist or is not a directory'
                }
            
            total_size = 0
            file_count = 0
            subdirectory_count = 0
            
            for item in path.rglob('*'):
                if item.is_file():
                    try:
                        total_size += item.stat().st_size
                        file_count += 1
                    except (OSError, IOError):
                        # Пропускаем файлы, к которым нет доступа
                        continue
                elif item.is_dir() and item != path:
                    subdirectory_count += 1
            
            return {
                'size_bytes': total_size,
                'size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'subdirectory_count': subdirectory_count
            }
            
        except Exception as e:
            monitoring_logger.error(f"Error calculating directory size for {path}: {e}")
            return {
                'size_bytes': 0,
                'file_count': 0,
                'subdirectory_count': 0,
                'error': str(e)
            }
    
    def get_media_usage_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить детальную разбивку использования медиа-папки.
        
        Returns:
            Dict[str, Dict[str, Any]]: Разбивка по категориям
        """
        try:
            breakdown = {}
            
            # Основные категории
            categories = {
                'users': self.media_root / 'users',
                'teams': self.media_root / 'teams',
                'temp': self.media_root / 'temp',
                'backups': self.media_root / 'backups'
            }
            
            for category, path in categories.items():
                breakdown[category] = self.get_directory_size(path)
            
            # Общая статистика
            breakdown['total'] = self.get_directory_size(self.media_root)
            breakdown['disk_usage'] = self.get_disk_usage()
            
            return breakdown
            
        except Exception as e:
            monitoring_logger.error(f"Error getting media usage breakdown: {e}")
            return {'error': str(e)}
    
    def get_user_storage_usage(self, user_id: int) -> Dict[str, Any]:
        """
        Получить информацию об использовании хранилища конкретным пользователем.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Dict[str, Any]: Статистика использования хранилища
        """
        try:
            user_path = self.media_root / 'users' / str(user_id)
            user_stats = self.get_directory_size(user_path)
            
            # Дополнительная информация о файлах пользователя
            file_types = {}
            if user_path.exists():
                for file_path in user_path.rglob('*'):
                    if file_path.is_file():
                        suffix = file_path.suffix.lower()
                        if suffix not in file_types:
                            file_types[suffix] = {'count': 0, 'size': 0}
                        
                        try:
                            file_size = file_path.stat().st_size
                            file_types[suffix]['count'] += 1
                            file_types[suffix]['size'] += file_size
                        except (OSError, IOError):
                            continue
            
            return {
                **user_stats,
                'file_types': file_types,
                'user_id': user_id
            }
            
        except Exception as e:
            monitoring_logger.error(f"Error getting user storage usage for user {user_id}: {e}")
            return {'error': str(e), 'user_id': user_id}
    
    def get_team_storage_usage(self, team_id: int) -> Dict[str, Any]:
        """
        Получить информацию об использовании хранилища командой.
        
        Args:
            team_id: ID команды
            
        Returns:
            Dict[str, Any]: Статистика использования хранилища
        """
        try:
            team_path = self.media_root / 'teams' / str(team_id)
            team_stats = self.get_directory_size(team_path)
            
            # Разбивка по проектам
            projects_breakdown = {}
            projects_path = team_path / 'projects'
            
            if projects_path.exists():
                for project_dir in projects_path.iterdir():
                    if project_dir.is_dir():
                        project_stats = self.get_directory_size(project_dir)
                        projects_breakdown[project_dir.name] = project_stats
            
            return {
                **team_stats,
                'projects': projects_breakdown,
                'team_id': team_id
            }
            
        except Exception as e:
            monitoring_logger.error(f"Error getting team storage usage for team {team_id}: {e}")
            return {'error': str(e), 'team_id': team_id}
    
    def get_cached_metrics(self) -> Dict[str, Any]:
        """
        Получить кэшированные метрики или обновить кэш при необходимости.
        
        Returns:
            Dict[str, Any]: Кэшированные метрики
        """
        now = timezone.now()
        
        # Проверяем, нужно ли обновить кэш
        if (self.last_cache_update is None or 
            (now - self.last_cache_update).total_seconds() > self.cache_timeout):
            
            self.metrics_cache = {
                'timestamp': now.isoformat(),
                'media_breakdown': self.get_media_usage_breakdown(),
                'disk_usage': self.get_disk_usage(),
            }
            self.last_cache_update = now
            
            monitoring_logger.info("File system metrics cache updated")
        
        return self.metrics_cache


class FileOperationMonitor:
    """
    Класс для мониторинга файловых операций и обнаружения аномалий.
    
    Отслеживает частоту операций, размеры файлов, ошибки и подозрительную активность.
    """
    
    def __init__(self):
        self.operation_stats = {}
        self.error_stats = {}
        self.alert_thresholds = {
            'max_operations_per_minute': 100,
            'max_file_size_mb': 50,
            'max_errors_per_hour': 10,
            'suspicious_file_patterns': ['.exe', '.bat', '.cmd', '.scr']
        }
    
    def record_operation(self, operation_type: str, user_id: Optional[int] = None, 
                        file_size: int = 0, file_path: str = '', success: bool = True):
        """
        Записать информацию о файловой операции.
        
        Args:
            operation_type: Тип операции
            user_id: ID пользователя
            file_size: Размер файла
            file_path: Путь к файлу
            success: Успешность операции
        """
        try:
            timestamp = timezone.now()
            
            # Инициализируем статистику для типа операции
            if operation_type not in self.operation_stats:
                self.operation_stats[operation_type] = {
                    'total_count': 0,
                    'success_count': 0,
                    'error_count': 0,
                    'total_size': 0,
                    'recent_operations': []
                }
            
            stats = self.operation_stats[operation_type]
            
            # Обновляем статистику
            stats['total_count'] += 1
            if success:
                stats['success_count'] += 1
            else:
                stats['error_count'] += 1
            
            stats['total_size'] += file_size
            
            # Добавляем в список недавних операций
            operation_record = {
                'timestamp': timestamp.isoformat(),
                'user_id': user_id,
                'file_size': file_size,
                'file_path': file_path,
                'success': success
            }
            
            stats['recent_operations'].append(operation_record)
            
            # Ограничиваем размер списка недавних операций
            if len(stats['recent_operations']) > 100:
                stats['recent_operations'] = stats['recent_operations'][-100:]
            
            # Проверяем на аномалии
            self._check_for_anomalies(operation_type, operation_record)
            
        except Exception as e:
            monitoring_logger.error(f"Error recording operation {operation_type}: {e}")
    
    def record_error(self, error_type: str, error_message: str, user_id: Optional[int] = None,
                    file_path: str = '', context: Dict[str, Any] = None):
        """
        Записать информацию об ошибке файловой операции.
        
        Args:
            error_type: Тип ошибки
            error_message: Сообщение об ошибке
            user_id: ID пользователя
            file_path: Путь к файлу
            context: Дополнительный контекст
        """
        try:
            timestamp = timezone.now()
            
            # Инициализируем статистику для типа ошибки
            if error_type not in self.error_stats:
                self.error_stats[error_type] = {
                    'count': 0,
                    'recent_errors': []
                }
            
            error_stats = self.error_stats[error_type]
            error_stats['count'] += 1
            
            # Добавляем в список недавних ошибок
            error_record = {
                'timestamp': timestamp.isoformat(),
                'message': error_message,
                'user_id': user_id,
                'file_path': file_path,
                'context': context or {}
            }
            
            error_stats['recent_errors'].append(error_record)
            
            # Ограничиваем размер списка недавних ошибок
            if len(error_stats['recent_errors']) > 50:
                error_stats['recent_errors'] = error_stats['recent_errors'][-50:]
            
            # Проверяем на критические ошибки
            self._check_critical_errors(error_type, error_record)
            
        except Exception as e:
            monitoring_logger.error(f"Error recording error {error_type}: {e}")
    
    def _check_for_anomalies(self, operation_type: str, operation_record: Dict[str, Any]):
        """
        Проверить операцию на аномалии.
        
        Args:
            operation_type: Тип операции
            operation_record: Запись об операции
        """
        try:
            # Проверка размера файла
            file_size_mb = operation_record['file_size'] / (1024 * 1024)
            if file_size_mb > self.alert_thresholds['max_file_size_mb']:
                self._send_anomaly_alert(
                    'large_file_upload',
                    f"Large file uploaded: {file_size_mb:.2f}MB",
                    operation_record
                )
            
            # Проверка подозрительных расширений файлов
            file_path = operation_record.get('file_path', '')
            for suspicious_pattern in self.alert_thresholds['suspicious_file_patterns']:
                if file_path.lower().endswith(suspicious_pattern):
                    self._send_anomaly_alert(
                        'suspicious_file_type',
                        f"Suspicious file type uploaded: {file_path}",
                        operation_record
                    )
                    break
            
            # Проверка частоты операций
            recent_ops = self.operation_stats[operation_type]['recent_operations']
            one_minute_ago = timezone.now() - timedelta(minutes=1)
            
            recent_count = sum(1 for op in recent_ops 
                             if datetime.fromisoformat(op['timestamp'].replace('Z', '+00:00')) > one_minute_ago)
            
            if recent_count > self.alert_thresholds['max_operations_per_minute']:
                self._send_anomaly_alert(
                    'high_operation_frequency',
                    f"High operation frequency: {recent_count} {operation_type} operations in last minute",
                    operation_record
                )
                
        except Exception as e:
            monitoring_logger.error(f"Error checking for anomalies: {e}")
    
    def _check_critical_errors(self, error_type: str, error_record: Dict[str, Any]):
        """
        Проверить ошибку на критичность.
        
        Args:
            error_type: Тип ошибки
            error_record: Запись об ошибке
        """
        try:
            # Критические типы ошибок
            critical_error_types = [
                'permission_denied',
                'disk_full',
                'security_violation',
                'data_corruption'
            ]
            
            if error_type in critical_error_types:
                self._send_critical_error_alert(error_type, error_record)
            
            # Проверка частоты ошибок
            recent_errors = self.error_stats[error_type]['recent_errors']
            one_hour_ago = timezone.now() - timedelta(hours=1)
            
            recent_error_count = sum(1 for err in recent_errors 
                                   if datetime.fromisoformat(err['timestamp'].replace('Z', '+00:00')) > one_hour_ago)
            
            if recent_error_count > self.alert_thresholds['max_errors_per_hour']:
                self._send_critical_error_alert(
                    'high_error_frequency',
                    {
                        **error_record,
                        'error_count': recent_error_count,
                        'error_type': error_type
                    }
                )
                
        except Exception as e:
            monitoring_logger.error(f"Error checking critical errors: {e}")
    
    def _send_anomaly_alert(self, anomaly_type: str, message: str, context: Dict[str, Any]):
        """
        Отправить уведомление об аномалии.
        
        Args:
            anomaly_type: Тип аномалии
            message: Сообщение
            context: Контекст
        """
        try:
            monitoring_logger.warning(f"File operation anomaly detected: {anomaly_type} - {message}")
            
            # Отправляем уведомление администраторам для критических аномалий
            if anomaly_type in ['suspicious_file_type', 'high_operation_frequency']:
                subject = f"[TranslationHub] File Operation Anomaly: {anomaly_type}"
                email_message = f"""
File operation anomaly detected:

Type: {anomaly_type}
Message: {message}
Timestamp: {context.get('timestamp', 'unknown')}
User ID: {context.get('user_id', 'unknown')}
File Path: {context.get('file_path', 'unknown')}
File Size: {context.get('file_size', 0)} bytes

Please investigate this activity.
                """
                
                mail_admins(subject, email_message, fail_silently=True)
                
        except Exception as e:
            monitoring_logger.error(f"Error sending anomaly alert: {e}")
    
    def _send_critical_error_alert(self, error_type: str, error_record: Dict[str, Any]):
        """
        Отправить уведомление о критической ошибке.
        
        Args:
            error_type: Тип ошибки
            error_record: Запись об ошибке
        """
        try:
            monitoring_logger.error(f"Critical file operation error: {error_type}")
            
            subject = f"[TranslationHub] CRITICAL: File Operation Error - {error_type}"
            message = f"""
CRITICAL FILE OPERATION ERROR:

Error Type: {error_type}
Message: {error_record.get('message', 'No message')}
Timestamp: {error_record.get('timestamp', 'unknown')}
User ID: {error_record.get('user_id', 'unknown')}
File Path: {error_record.get('file_path', 'unknown')}

Context: {json.dumps(error_record.get('context', {}), indent=2)}

IMMEDIATE ACTION REQUIRED!
            """
            
            mail_admins(subject, message, fail_silently=True)
            
        except Exception as e:
            monitoring_logger.error(f"Error sending critical error alert: {e}")
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """
        Получить статистику файловых операций.
        
        Returns:
            Dict[str, Any]: Статистика операций
        """
        try:
            return {
                'timestamp': timezone.now().isoformat(),
                'operations': self.operation_stats,
                'errors': self.error_stats,
                'alert_thresholds': self.alert_thresholds
            }
        except Exception as e:
            monitoring_logger.error(f"Error getting operation statistics: {e}")
            return {'error': str(e)}


# Глобальные экземпляры для использования в приложении
file_metrics = FileSystemMetrics()
operation_monitor = FileOperationMonitor()


class OrphanedFileCleanup:
    """
    Класс для поиска и очистки осиротевших файлов.
    
    Находит файлы, которые больше не связаны с объектами в базе данных,
    и безопасно удаляет их с соответствующим логированием.
    """
    
    def __init__(self):
        self.media_root = Path(settings.MEDIA_ROOT)
        self.cleanup_stats = {
            'files_checked': 0,
            'orphaned_files_found': 0,
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
    
    def find_orphaned_user_files(self) -> List[Dict[str, Any]]:
        """
        Найти осиротевшие файлы пользователей.
        
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов
        """
        orphaned_files = []
        
        try:
            users_path = self.media_root / 'users'
            if not users_path.exists():
                return orphaned_files
            
            # Получаем список всех активных пользователей
            User, _, _, _ = _get_models()
            if User:
                active_user_ids = set(User.objects.values_list('id', flat=True))
            else:
                monitoring_logger.warning("User model not available for orphaned file cleanup")
                return orphaned_files
            
            # Проверяем каждую папку пользователя
            for user_dir in users_path.iterdir():
                if not user_dir.is_dir():
                    continue
                
                try:
                    user_id = int(user_dir.name)
                    
                    # Если пользователь не существует, помечаем папку как осиротевшую
                    if user_id not in active_user_ids:
                        orphaned_files.append({
                            'type': 'user_directory',
                            'path': user_dir,
                            'user_id': user_id,
                            'size': self._get_directory_size(user_dir),
                            'reason': 'User no longer exists'
                        })
                    else:
                        # Проверяем файлы внутри папки пользователя
                        user_orphaned = self._check_user_directory_files(user_dir, user_id)
                        orphaned_files.extend(user_orphaned)
                        
                except (ValueError, OSError) as e:
                    monitoring_logger.warning(f"Error processing user directory {user_dir}: {e}")
                    continue
            
        except Exception as e:
            monitoring_logger.error(f"Error finding orphaned user files: {e}")
            self.cleanup_stats['errors'].append(f"User files scan error: {e}")
        
        return orphaned_files
    
    def find_orphaned_team_files(self) -> List[Dict[str, Any]]:
        """
        Найти осиротевшие файлы команд.
        
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов
        """
        orphaned_files = []
        
        try:
            teams_path = self.media_root / 'teams'
            if not teams_path.exists():
                return orphaned_files
            
            # Получаем список всех активных команд
            _, Team, _, _ = _get_models()
            if Team:
                active_team_ids = set(Team.objects.values_list('id', flat=True))
            else:
                monitoring_logger.warning("Team model not available for orphaned file cleanup")
                return orphaned_files
            
            # Проверяем каждую папку команды
            for team_dir in teams_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                try:
                    team_id = int(team_dir.name)
                    
                    # Если команда не существует, помечаем папку как осиротевшую
                    if team_id not in active_team_ids:
                        orphaned_files.append({
                            'type': 'team_directory',
                            'path': team_dir,
                            'team_id': team_id,
                            'size': self._get_directory_size(team_dir),
                            'reason': 'Team no longer exists'
                        })
                    else:
                        # Проверяем проекты внутри папки команды
                        team_orphaned = self._check_team_directory_files(team_dir, team_id)
                        orphaned_files.extend(team_orphaned)
                        
                except (ValueError, OSError) as e:
                    monitoring_logger.warning(f"Error processing team directory {team_dir}: {e}")
                    continue
            
        except Exception as e:
            monitoring_logger.error(f"Error finding orphaned team files: {e}")
            self.cleanup_stats['errors'].append(f"Team files scan error: {e}")
        
        return orphaned_files
    
    def find_orphaned_project_files(self) -> List[Dict[str, Any]]:
        """
        Найти осиротевшие файлы проектов.
        
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов
        """
        orphaned_files = []
        
        try:
            _, _, Project, _ = _get_models()
            if not Project:
                monitoring_logger.warning("Project model not available for orphaned file cleanup")
                return orphaned_files
            
            # Получаем список всех активных проектов с их папками
            active_projects = {}
            for project in Project.objects.select_related('team').all():
                team_id = project.team.id
                content_folder = project.content_folder
                
                if team_id not in active_projects:
                    active_projects[team_id] = set()
                active_projects[team_id].add(content_folder)
            
            # Проверяем папки проектов
            teams_path = self.media_root / 'teams'
            if not teams_path.exists():
                return orphaned_files
            
            for team_dir in teams_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                try:
                    team_id = int(team_dir.name)
                    projects_path = team_dir / 'projects'
                    
                    if not projects_path.exists():
                        continue
                    
                    # Проверяем каждую папку проекта
                    for project_dir in projects_path.iterdir():
                        if not project_dir.is_dir():
                            continue
                        
                        project_folder = project_dir.name
                        
                        # Если проект не существует, помечаем папку как осиротевшую
                        if (team_id not in active_projects or 
                            project_folder not in active_projects[team_id]):
                            
                            orphaned_files.append({
                                'type': 'project_directory',
                                'path': project_dir,
                                'team_id': team_id,
                                'project_folder': project_folder,
                                'size': self._get_directory_size(project_dir),
                                'reason': 'Project no longer exists'
                            })
                        
                except (ValueError, OSError) as e:
                    monitoring_logger.warning(f"Error processing project directories in {team_dir}: {e}")
                    continue
            
        except Exception as e:
            monitoring_logger.error(f"Error finding orphaned project files: {e}")
            self.cleanup_stats['errors'].append(f"Project files scan error: {e}")
        
        return orphaned_files
    
    def find_orphaned_image_files(self) -> List[Dict[str, Any]]:
        """
        Найти осиротевшие файлы изображений.
        
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов изображений
        """
        orphaned_files = []
        
        try:
            _, _, _, ImageContent = _get_models()
            if not ImageContent:
                monitoring_logger.warning("ImageContent model not available for orphaned file cleanup")
                return orphaned_files
            
            # Получаем список всех активных изображений
            active_image_paths = set()
            for image_content in ImageContent.objects.all():
                if image_content.image:
                    # Нормализуем путь
                    image_path = str(image_content.image).replace('\\', '/')
                    active_image_paths.add(image_path)
            
            # Проверяем файлы изображений в папках проектов
            teams_path = self.media_root / 'teams'
            if not teams_path.exists():
                return orphaned_files
            
            for team_dir in teams_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                projects_path = team_dir / 'projects'
                if not projects_path.exists():
                    continue
                
                for project_dir in projects_path.iterdir():
                    if not project_dir.is_dir():
                        continue
                    
                    images_path = project_dir / 'images'
                    if not images_path.exists():
                        continue
                    
                    # Проверяем каждый файл изображения
                    for image_file in images_path.rglob('*'):
                        if not image_file.is_file():
                            continue
                        
                        # Получаем относительный путь от MEDIA_ROOT
                        try:
                            relative_path = str(image_file.relative_to(self.media_root)).replace('\\', '/')
                            
                            if relative_path not in active_image_paths:
                                orphaned_files.append({
                                    'type': 'orphaned_image',
                                    'path': image_file,
                                    'relative_path': relative_path,
                                    'size': image_file.stat().st_size,
                                    'reason': 'Image not referenced in database'
                                })
                                
                        except (ValueError, OSError) as e:
                            monitoring_logger.warning(f"Error processing image file {image_file}: {e}")
                            continue
            
        except Exception as e:
            monitoring_logger.error(f"Error finding orphaned image files: {e}")
            self.cleanup_stats['errors'].append(f"Image files scan error: {e}")
        
        return orphaned_files
    
    def find_temporary_files(self, max_age_hours: int = 24) -> List[Dict[str, Any]]:
        """
        Найти временные файлы старше указанного возраста.
        
        Args:
            max_age_hours: Максимальный возраст файлов в часах
            
        Returns:
            List[Dict[str, Any]]: Список временных файлов для удаления
        """
        temp_files = []
        
        try:
            temp_path = self.media_root / 'temp'
            if not temp_path.exists():
                return temp_files
            
            cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
            
            for temp_file in temp_path.rglob('*'):
                if not temp_file.is_file():
                    continue
                
                try:
                    # Получаем время модификации файла
                    mtime = datetime.fromtimestamp(temp_file.stat().st_mtime, tz=timezone.utc)
                    
                    if mtime < cutoff_time:
                        temp_files.append({
                            'type': 'temporary_file',
                            'path': temp_file,
                            'size': temp_file.stat().st_size,
                            'age_hours': (timezone.now() - mtime).total_seconds() / 3600,
                            'reason': f'Temporary file older than {max_age_hours} hours'
                        })
                        
                except (OSError, IOError) as e:
                    monitoring_logger.warning(f"Error processing temporary file {temp_file}: {e}")
                    continue
            
        except Exception as e:
            monitoring_logger.error(f"Error finding temporary files: {e}")
            self.cleanup_stats['errors'].append(f"Temporary files scan error: {e}")
        
        return temp_files
    
    def _check_user_directory_files(self, user_dir: Path, user_id: int) -> List[Dict[str, Any]]:
        """
        Проверить файлы в папке пользователя на осиротевшие.
        
        Args:
            user_dir: Путь к папке пользователя
            user_id: ID пользователя
            
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов
        """
        orphaned_files = []
        
        try:
            User, _, _, _ = _get_models()
            if not User:
                return orphaned_files
            
            # Получаем пользователя
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return orphaned_files
            
            # Проверяем аватарку
            avatar_path = user_dir / 'avatar.jpg'
            if avatar_path.exists() and not user.avatar:
                orphaned_files.append({
                    'type': 'orphaned_avatar',
                    'path': avatar_path,
                    'user_id': user_id,
                    'size': avatar_path.stat().st_size,
                    'reason': 'Avatar file exists but not referenced in user model'
                })
            
            # Проверяем другие файлы в папке пользователя
            for file_path in user_dir.rglob('*'):
                if file_path.is_file() and file_path != avatar_path:
                    # Дополнительная логика проверки других файлов пользователя
                    # может быть добавлена здесь при необходимости
                    pass
            
        except Exception as e:
            monitoring_logger.warning(f"Error checking user directory files for user {user_id}: {e}")
        
        return orphaned_files
    
    def _check_team_directory_files(self, team_dir: Path, team_id: int) -> List[Dict[str, Any]]:
        """
        Проверить файлы в папке команды на осиротевшие.
        
        Args:
            team_dir: Путь к папке команды
            team_id: ID команды
            
        Returns:
            List[Dict[str, Any]]: Список осиротевших файлов
        """
        orphaned_files = []
        
        try:
            # Проверяем документы команды
            documents_path = team_dir / 'documents'
            if documents_path.exists():
                for doc_file in documents_path.rglob('*'):
                    if doc_file.is_file():
                        # Логика проверки документов команды
                        # может быть добавлена здесь при необходимости
                        pass
            
        except Exception as e:
            monitoring_logger.warning(f"Error checking team directory files for team {team_id}: {e}")
        
        return orphaned_files
    
    def _get_directory_size(self, path: Path) -> int:
        """
        Получить размер директории в байтах.
        
        Args:
            path: Путь к директории
            
        Returns:
            int: Размер в байтах
        """
        try:
            total_size = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except (OSError, IOError):
                        continue
            return total_size
        except Exception:
            return 0
    
    def cleanup_orphaned_files(self, dry_run: bool = True, 
                              file_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Очистить осиротевшие файлы.
        
        Args:
            dry_run: Если True, только показать что будет удалено
            file_types: Типы файлов для очистки (по умолчанию все)
            
        Returns:
            Dict[str, Any]: Результаты очистки
        """
        # Сброс статистики
        self.cleanup_stats = {
            'files_checked': 0,
            'orphaned_files_found': 0,
            'files_deleted': 0,
            'space_freed': 0,
            'errors': [],
            'dry_run': dry_run
        }
        
        try:
            all_orphaned_files = []
            
            # Определяем какие типы файлов проверять
            if file_types is None:
                file_types = ['user', 'team', 'project', 'image', 'temporary']
            
            # Поиск осиротевших файлов по типам
            if 'user' in file_types:
                all_orphaned_files.extend(self.find_orphaned_user_files())
            
            if 'team' in file_types:
                all_orphaned_files.extend(self.find_orphaned_team_files())
            
            if 'project' in file_types:
                all_orphaned_files.extend(self.find_orphaned_project_files())
            
            if 'image' in file_types:
                all_orphaned_files.extend(self.find_orphaned_image_files())
            
            if 'temporary' in file_types:
                all_orphaned_files.extend(self.find_temporary_files())
            
            self.cleanup_stats['orphaned_files_found'] = len(all_orphaned_files)
            
            # Удаление файлов
            deleted_files = []
            for file_info in all_orphaned_files:
                try:
                    file_path = file_info['path']
                    file_size = file_info['size']
                    
                    if not dry_run:
                        if file_path.is_file():
                            file_path.unlink()
                            file_logger.info(f"Deleted orphaned file: {file_path}")
                        elif file_path.is_dir():
                            shutil.rmtree(file_path)
                            file_logger.info(f"Deleted orphaned directory: {file_path}")
                        
                        self.cleanup_stats['files_deleted'] += 1
                        self.cleanup_stats['space_freed'] += file_size
                    
                    deleted_files.append({
                        'path': str(file_path),
                        'type': file_info['type'],
                        'size': file_size,
                        'reason': file_info['reason'],
                        'deleted': not dry_run
                    })
                    
                except Exception as e:
                    error_msg = f"Error deleting {file_path}: {e}"
                    monitoring_logger.error(error_msg)
                    self.cleanup_stats['errors'].append(error_msg)
            
            # Логирование результатов
            if dry_run:
                monitoring_logger.info(f"Dry run completed: found {len(all_orphaned_files)} orphaned files")
            else:
                monitoring_logger.info(f"Cleanup completed: deleted {self.cleanup_stats['files_deleted']} files, "
                                     f"freed {self.cleanup_stats['space_freed']} bytes")
            
            return {
                'success': True,
                'statistics': self.cleanup_stats,
                'deleted_files': deleted_files,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Error during orphaned file cleanup: {e}"
            monitoring_logger.error(error_msg)
            self.cleanup_stats['errors'].append(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'statistics': self.cleanup_stats,
                'timestamp': timezone.now().isoformat()
            }


# Глобальный экземпляр для использования в приложении
orphaned_cleanup = OrphanedFileCleanup()