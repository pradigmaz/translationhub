"""
Утилиты для управления файловой структурой TranslationHub.

Этот модуль содержит классы для организованного управления файлами и папками
в иерархической структуре, обеспечивая изоляцию данных между пользователями,
командами и проектами.
"""

import os
import shutil
import logging
import traceback
from pathlib import Path
from typing import Optional, Union, Dict, Any
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.core.mail import mail_admins
from django.utils import timezone

# Импортируем мониторинг (с отложенным импортом для избежания циклических зависимостей)
try:
    from .file_monitoring import operation_monitor
except ImportError:
    operation_monitor = None


# Настройка логирования для файловых операций
file_logger = logging.getLogger('file_operations')
security_logger = logging.getLogger('security')


class FileSystemError(Exception):
    """Базовое исключение для ошибок файловой системы"""
    
    def __init__(self, message: str, path: Optional[Union[str, Path]] = None, 
                 original_error: Optional[Exception] = None, **kwargs):
        super().__init__(message)
        self.path = str(path) if path else None
        self.original_error = original_error
        self.timestamp = timezone.now()
        self.extra_data = kwargs
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать исключение в словарь для логирования"""
        return {
            'error_type': self.__class__.__name__,
            'message': str(self),
            'path': self.path,
            'timestamp': self.timestamp.isoformat(),
            'original_error': str(self.original_error) if self.original_error else None,
            'traceback': traceback.format_exc() if self.original_error else None,
            **self.extra_data
        }


class DirectoryCreationError(FileSystemError):
    """Ошибка создания папки"""
    
    def __init__(self, message: str, path: Optional[Union[str, Path]] = None, 
                 original_error: Optional[Exception] = None, permissions: Optional[str] = None):
        super().__init__(message, path, original_error, permissions=permissions)


class FileUploadError(FileSystemError):
    """Ошибка загрузки файла"""
    
    def __init__(self, message: str, path: Optional[Union[str, Path]] = None,
                 original_error: Optional[Exception] = None, file_size: Optional[int] = None,
                 file_type: Optional[str] = None, user_id: Optional[int] = None):
        super().__init__(message, path, original_error, 
                        file_size=file_size, file_type=file_type, user_id=user_id)


class FileCleanupError(FileSystemError):
    """Ошибка очистки файлов"""
    
    def __init__(self, message: str, path: Optional[Union[str, Path]] = None,
                 original_error: Optional[Exception] = None, cleanup_type: Optional[str] = None):
        super().__init__(message, path, original_error, cleanup_type=cleanup_type)


class FileValidationError(FileSystemError):
    """Ошибка валидации файла"""
    
    def __init__(self, message: str, filename: Optional[str] = None,
                 original_error: Optional[Exception] = None, validation_type: Optional[str] = None):
        super().__init__(message, filename, original_error, validation_type=validation_type)


class FileSecurityError(FileSystemError):
    """Ошибка безопасности файловых операций"""
    
    def __init__(self, message: str, path: Optional[Union[str, Path]] = None,
                 original_error: Optional[Exception] = None, user_id: Optional[int] = None,
                 ip_address: Optional[str] = None):
        super().__init__(message, path, original_error, user_id=user_id, ip_address=ip_address)


class FileOperationLogger:
    """Расширенный логгер для файловых операций с уведомлениями администраторов"""
    
    # Критические операции, требующие уведомления администраторов
    CRITICAL_OPERATIONS = {
        'directory_creation_failed',
        'file_upload_security_violation',
        'file_cleanup_failed',
        'disk_space_critical',
        'permission_denied'
    }
    
    @staticmethod
    def log_directory_created(path: Union[str, Path], user_id: Optional[int] = None, 
                            operation_context: Optional[str] = None):
        """Логирование создания папки"""
        log_data = {
            'operation': 'directory_created',
            'path': str(path),
            'user_id': user_id,
            'context': operation_context,
            'timestamp': timezone.now().isoformat()
        }
        file_logger.info(f"Directory created: {path} by user {user_id} (context: {operation_context})", 
                        extra=log_data)
        
        # Записываем в систему мониторинга
        if operation_monitor:
            operation_monitor.record_operation(
                'directory_creation',
                user_id=user_id,
                file_path=str(path),
                success=True
            )
    
    @staticmethod
    def log_file_uploaded(path: Union[str, Path], user_id: Optional[int], file_size: int,
                         file_type: Optional[str] = None, operation_context: Optional[str] = None):
        """Логирование загрузки файла"""
        log_data = {
            'operation': 'file_uploaded',
            'path': str(path),
            'user_id': user_id,
            'file_size': file_size,
            'file_type': file_type,
            'context': operation_context,
            'timestamp': timezone.now().isoformat()
        }
        file_logger.info(f"File uploaded: {path} by user {user_id}, size: {file_size}, type: {file_type}", 
                        extra=log_data)
        
        # Записываем в систему мониторинга
        if operation_monitor:
            operation_monitor.record_operation(
                'file_upload',
                user_id=user_id,
                file_size=file_size,
                file_path=str(path),
                success=True
            )
    
    @staticmethod
    def log_file_deleted(path: Union[str, Path], user_id: Optional[int] = None,
                        operation_context: Optional[str] = None):
        """Логирование удаления файла"""
        log_data = {
            'operation': 'file_deleted',
            'path': str(path),
            'user_id': user_id,
            'context': operation_context,
            'timestamp': timezone.now().isoformat()
        }
        file_logger.info(f"File deleted: {path} by user {user_id} (context: {operation_context})", 
                        extra=log_data)
        
        # Записываем в систему мониторинга
        if operation_monitor:
            operation_monitor.record_operation(
                'file_deletion',
                user_id=user_id,
                file_path=str(path),
                success=True
            )
    
    @staticmethod
    def log_error(operation: str, error: Exception, path: Optional[Union[str, Path]] = None,
                 user_id: Optional[int] = None, notify_admins: bool = False):
        """Расширенное логирование ошибок с возможностью уведомления администраторов"""
        
        # Подготавливаем данные для логирования
        error_data = {
            'operation': operation,
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'path': str(path) if path else None,
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
            'traceback': traceback.format_exc()
        }
        
        # Если это FileSystemError, добавляем дополнительные данные
        if isinstance(error, FileSystemError):
            error_data.update(error.to_dict())
        
        # Логируем ошибку
        file_logger.error(f"Error in {operation}: {error}, path: {path}, user: {user_id}", 
                         extra=error_data)
        
        # Записываем ошибку в систему мониторинга
        if operation_monitor:
            operation_monitor.record_error(
                operation,
                str(error),
                user_id=user_id,
                file_path=str(path) if path else '',
                context=error_data
            )
        
        # Проверяем, нужно ли уведомить администраторов
        if notify_admins or operation in FileOperationLogger.CRITICAL_OPERATIONS:
            FileOperationLogger._notify_admins_about_error(operation, error, error_data)
    
    @staticmethod
    def log_security_violation(operation: str, path: Union[str, Path], user_id: Optional[int] = None,
                              ip_address: Optional[str] = None, details: Optional[str] = None):
        """Логирование нарушений безопасности"""
        security_data = {
            'operation': 'security_violation',
            'violation_type': operation,
            'path': str(path),
            'user_id': user_id,
            'ip_address': ip_address,
            'details': details,
            'timestamp': timezone.now().isoformat()
        }
        
        # Логируем в security лог
        security_logger.warning(f"Security violation in {operation}: {details}, path: {path}, "
                               f"user: {user_id}, IP: {ip_address}", extra=security_data)
        
        # Также логируем в файловые операции
        file_logger.warning(f"Security violation: {operation} - {details}", extra=security_data)
        
        # Всегда уведомляем администраторов о нарушениях безопасности
        FileOperationLogger._notify_admins_about_security_violation(operation, security_data)
    
    @staticmethod
    def log_disk_space_warning(path: Union[str, Path], available_space: int, threshold: int):
        """Логирование предупреждений о нехватке места на диске"""
        warning_data = {
            'operation': 'disk_space_warning',
            'path': str(path),
            'available_space': available_space,
            'threshold': threshold,
            'timestamp': timezone.now().isoformat()
        }
        
        file_logger.warning(f"Low disk space warning: {available_space} bytes available at {path}, "
                           f"threshold: {threshold}", extra=warning_data)
        
        # Уведомляем администраторов о критически низком месте на диске
        if available_space < threshold * 0.5:  # Менее 50% от порога
            FileOperationLogger._notify_admins_about_disk_space(warning_data)
    
    @staticmethod
    def _notify_admins_about_error(operation: str, error: Exception, error_data: Dict[str, Any]):
        """Отправить уведомление администраторам об ошибке"""
        try:
            subject = f"[TranslationHub] Critical File System Error: {operation}"
            message = f"""
Critical file system error occurred:

Operation: {operation}
Error Type: {error.__class__.__name__}
Error Message: {str(error)}
Path: {error_data.get('path', 'N/A')}
User ID: {error_data.get('user_id', 'N/A')}
Timestamp: {error_data.get('timestamp', 'N/A')}

Traceback:
{error_data.get('traceback', 'N/A')}

Please investigate this issue immediately.
            """
            
            mail_admins(subject, message, fail_silently=True)
            file_logger.info(f"Admin notification sent for error: {operation}")
            
        except Exception as e:
            file_logger.error(f"Failed to send admin notification: {e}")
    
    @staticmethod
    def _notify_admins_about_security_violation(operation: str, security_data: Dict[str, Any]):
        """Отправить уведомление администраторам о нарушении безопасности"""
        try:
            subject = f"[TranslationHub] SECURITY ALERT: {operation}"
            message = f"""
SECURITY VIOLATION DETECTED:

Violation Type: {operation}
Path: {security_data.get('path', 'N/A')}
User ID: {security_data.get('user_id', 'N/A')}
IP Address: {security_data.get('ip_address', 'N/A')}
Details: {security_data.get('details', 'N/A')}
Timestamp: {security_data.get('timestamp', 'N/A')}

IMMEDIATE ACTION REQUIRED!
            """
            
            mail_admins(subject, message, fail_silently=True)
            security_logger.info(f"Security alert sent to admins for: {operation}")
            
        except Exception as e:
            security_logger.error(f"Failed to send security alert: {e}")
    
    @staticmethod
    def _notify_admins_about_disk_space(warning_data: Dict[str, Any]):
        """Отправить уведомление администраторам о нехватке места на диске"""
        try:
            subject = "[TranslationHub] CRITICAL: Low Disk Space"
            message = f"""
CRITICAL DISK SPACE WARNING:

Path: {warning_data.get('path', 'N/A')}
Available Space: {warning_data.get('available_space', 'N/A')} bytes
Threshold: {warning_data.get('threshold', 'N/A')} bytes
Timestamp: {warning_data.get('timestamp', 'N/A')}

Please free up disk space immediately to prevent system failures.
            """
            
            mail_admins(subject, message, fail_silently=True)
            file_logger.info("Disk space alert sent to admins")
            
        except Exception as e:
            file_logger.error(f"Failed to send disk space alert: {e}")


class FilePathManager:
    """
    Менеджер путей к файлам и папкам.
    
    Центральный компонент для генерации путей к файлам и папкам
    в соответствии с иерархической структурой системы.
    """
    
    @staticmethod
    def get_user_path(user_id: int) -> Path:
        """
        Получить путь к папке пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Path: Путь к папке пользователя
        """
        return Path(settings.MEDIA_ROOT) / "users" / str(user_id)
    
    @staticmethod
    def get_team_path(team_id: int) -> Path:
        """
        Получить путь к папке команды.
        
        Args:
            team_id: ID команды
            
        Returns:
            Path: Путь к папке команды
        """
        return Path(settings.MEDIA_ROOT) / "teams" / str(team_id)
    
    @staticmethod
    def get_project_path(team_id: int, content_folder: str) -> Path:
        """
        Получить путь к папке проекта.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            
        Returns:
            Path: Путь к папке проекта
        """
        return FilePathManager.get_team_path(team_id) / "projects" / content_folder
    
    @staticmethod
    def get_avatar_path(user_id: int) -> str:
        """
        Получить путь для сохранения аватарки пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            str: Относительный путь для upload_to
        """
        return f"users/{user_id}/avatar.jpg"
    
    @staticmethod
    def get_project_image_path(team_id: int, content_folder: str, filename: str) -> str:
        """
        Получить путь для сохранения изображения проекта.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            filename: Имя файла
            
        Returns:
            str: Относительный путь для upload_to
        """
        return f"teams/{team_id}/projects/{content_folder}/images/{filename}"
    
    @staticmethod
    def get_project_document_path(team_id: int, content_folder: str, filename: str) -> str:
        """
        Получить путь для сохранения документа проекта.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            filename: Имя файла
            
        Returns:
            str: Относительный путь для upload_to
        """
        return f"teams/{team_id}/projects/{content_folder}/documents/{filename}"
    
    @staticmethod
    def get_project_glossary_path(team_id: int, content_folder: str, filename: str) -> str:
        """
        Получить путь для сохранения файла глоссария проекта.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            filename: Имя файла
            
        Returns:
            str: Относительный путь для upload_to
        """
        return f"teams/{team_id}/projects/{content_folder}/glossary/{filename}"


class DirectoryManager:
    """
    Менеджер создания и управления папками.
    
    Компонент для создания, проверки существования и удаления папок
    с соответствующим логированием и обработкой ошибок.
    """
    
    @staticmethod
    def ensure_directory_exists(path: Union[str, Path], user_id: Optional[int] = None) -> bool:
        """
        Убедиться, что папка существует, создать если нет.
        
        Args:
            path: Путь к папке
            user_id: ID пользователя для логирования
            
        Returns:
            bool: True если папка существует или была создана успешно
            
        Raises:
            DirectoryCreationError: При критических ошибках создания папки
        """
        try:
            path = Path(path)
            
            # Проверяем безопасность пути
            if not FilePathValidator.validate_path_security(str(path.relative_to(settings.MEDIA_ROOT))):
                raise FileSecurityError(
                    f"Unsafe directory path detected: {path}",
                    path=path,
                    user_id=user_id
                )
            
            if not path.exists():
                # Проверяем доступное место на диске перед созданием
                DirectoryManager._check_disk_space(path.parent)
                
                # Создаем папку
                path.mkdir(parents=True, exist_ok=True)
                
                # Проверяем права доступа
                if not os.access(path, os.R_OK | os.W_OK):
                    raise DirectoryCreationError(
                        f"Created directory has insufficient permissions: {path}",
                        path=path,
                        permissions=oct(path.stat().st_mode)
                    )
                
                FileOperationLogger.log_directory_created(path, user_id, "ensure_directory_exists")
            
            return True
            
        except (FileSecurityError, DirectoryCreationError):
            # Перебрасываем наши исключения как есть
            raise
        except PermissionError as e:
            error = DirectoryCreationError(
                f"Permission denied creating directory: {path}",
                path=path,
                original_error=e,
                permissions="insufficient"
            )
            FileOperationLogger.log_error("ensure_directory_exists", error, path, user_id, notify_admins=True)
            raise error
        except OSError as e:
            error = DirectoryCreationError(
                f"OS error creating directory: {path}",
                path=path,
                original_error=e
            )
            FileOperationLogger.log_error("ensure_directory_exists", error, path, user_id, notify_admins=True)
            raise error
        except Exception as e:
            error = DirectoryCreationError(
                f"Unexpected error creating directory: {path}",
                path=path,
                original_error=e
            )
            FileOperationLogger.log_error("ensure_directory_exists", error, path, user_id, notify_admins=True)
            raise error
    
    @staticmethod
    def _check_disk_space(path: Path, min_free_bytes: int = 100 * 1024 * 1024):  # 100MB по умолчанию
        """
        Проверить доступное место на диске.
        
        Args:
            path: Путь для проверки
            min_free_bytes: Минимальное количество свободных байт
            
        Raises:
            DirectoryCreationError: Если недостаточно места на диске
        """
        try:
            stat = shutil.disk_usage(path)
            available_space = stat.free
            
            if available_space < min_free_bytes:
                FileOperationLogger.log_disk_space_warning(path, available_space, min_free_bytes)
                raise DirectoryCreationError(
                    f"Insufficient disk space: {available_space} bytes available, "
                    f"{min_free_bytes} bytes required",
                    path=path
                )
                
        except DirectoryCreationError:
            raise
        except Exception as e:
            # Если не можем проверить место на диске, логируем предупреждение но продолжаем
            FileOperationLogger.log_error("disk_space_check", e, path)
    
    @staticmethod
    def create_user_directory(user_id: int) -> bool:
        """
        Создать структуру папок для пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: True если структура создана успешно
            
        Raises:
            DirectoryCreationError: При ошибках создания структуры папок
        """
        try:
            user_path = FilePathManager.get_user_path(user_id)
            
            # Создаем основную папку пользователя
            DirectoryManager.ensure_directory_exists(user_path, user_id)
            
            # Создаем подпапку для документов
            documents_path = user_path / "documents"
            DirectoryManager.ensure_directory_exists(documents_path, user_id)
            
            FileOperationLogger.log_directory_created(user_path, user_id, "create_user_directory")
            return True
            
        except (FileSecurityError, DirectoryCreationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = DirectoryCreationError(
                f"Failed to create user directory for user {user_id}",
                path=FilePathManager.get_user_path(user_id),
                original_error=e
            )
            FileOperationLogger.log_error("create_user_directory", error, user_id=user_id, notify_admins=True)
            raise error
    
    @staticmethod
    def create_team_directory(team_id: int) -> bool:
        """
        Создать структуру папок для команды.
        
        Args:
            team_id: ID команды
            
        Returns:
            bool: True если структура создана успешно
            
        Raises:
            DirectoryCreationError: При ошибках создания структуры папок
        """
        try:
            team_path = FilePathManager.get_team_path(team_id)
            
            # Создаем основную папку команды
            DirectoryManager.ensure_directory_exists(team_path)
            
            # Создаем подпапки
            documents_path = team_path / "documents"
            projects_path = team_path / "projects"
            
            DirectoryManager.ensure_directory_exists(documents_path)
            DirectoryManager.ensure_directory_exists(projects_path)
            
            FileOperationLogger.log_directory_created(team_path, operation_context="create_team_directory")
            return True
            
        except (FileSecurityError, DirectoryCreationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = DirectoryCreationError(
                f"Failed to create team directory for team {team_id}",
                path=FilePathManager.get_team_path(team_id),
                original_error=e
            )
            FileOperationLogger.log_error("create_team_directory", error, notify_admins=True)
            raise error
    
    @staticmethod
    def create_project_directory(team_id: int, content_folder: str) -> bool:
        """
        Создать структуру папок для проекта.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            
        Returns:
            bool: True если структура создана успешно
            
        Raises:
            DirectoryCreationError: При ошибках создания структуры папок
        """
        try:
            # Валидируем имя папки проекта
            if not FilePathValidator.validate_filename(content_folder):
                raise FileValidationError(
                    f"Invalid project folder name: {content_folder}",
                    filename=content_folder,
                    validation_type="folder_name"
                )
            
            project_path = FilePathManager.get_project_path(team_id, content_folder)
            
            # Создаем основную папку проекта
            DirectoryManager.ensure_directory_exists(project_path)
            
            # Создаем подпапки проекта
            subdirs = ["images", "documents", "glossary"]
            for subdir in subdirs:
                subdir_path = project_path / subdir
                DirectoryManager.ensure_directory_exists(subdir_path)
            
            FileOperationLogger.log_directory_created(project_path, operation_context="create_project_directory")
            return True
            
        except (FileSecurityError, DirectoryCreationError, FileValidationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = DirectoryCreationError(
                f"Failed to create project directory for team {team_id}, project {content_folder}",
                path=FilePathManager.get_project_path(team_id, content_folder),
                original_error=e
            )
            FileOperationLogger.log_error("create_project_directory", error, notify_admins=True)
            raise error
    
    @staticmethod
    def remove_directory_safe(path: Union[str, Path], user_id: Optional[int] = None) -> bool:
        """
        Безопасно удалить папку с логированием.
        
        Args:
            path: Путь к папке для удаления
            user_id: ID пользователя для логирования
            
        Returns:
            bool: True если папка удалена успешно или не существовала
        """
        try:
            path = Path(path)
            
            # Проверяем безопасность пути
            if not FilePathValidator.validate_path_security(str(path.relative_to(settings.MEDIA_ROOT))):
                FileOperationLogger.log_security_violation(
                    "unsafe_directory_deletion",
                    path,
                    user_id=user_id,
                    details=f"Attempt to delete unsafe path: {path}"
                )
                return False
            
            if path.exists() and path.is_dir():
                # Проверяем, что папка не содержит критически важные файлы
                if DirectoryManager._contains_critical_files(path):
                    FileOperationLogger.log_error(
                        "remove_directory_safe",
                        FileCleanupError(f"Directory contains critical files: {path}", path=path),
                        path,
                        user_id,
                        notify_admins=True
                    )
                    return False
                
                # Удаляем папку
                shutil.rmtree(path)
                FileOperationLogger.log_file_deleted(path, user_id, "remove_directory_safe")
            
            return True
            
        except PermissionError as e:
            error = FileCleanupError(
                f"Permission denied deleting directory: {path}",
                path=path,
                original_error=e,
                cleanup_type="directory_removal"
            )
            FileOperationLogger.log_error("remove_directory_safe", error, path, user_id, notify_admins=True)
            return False
        except Exception as e:
            error = FileCleanupError(
                f"Error deleting directory: {path}",
                path=path,
                original_error=e,
                cleanup_type="directory_removal"
            )
            FileOperationLogger.log_error("remove_directory_safe", error, path, user_id)
            return False
    
    @staticmethod
    def _contains_critical_files(path: Path) -> bool:
        """
        Проверить, содержит ли папка критически важные файлы.
        
        Args:
            path: Путь к папке
            
        Returns:
            bool: True если папка содержит критически важные файлы
        """
        try:
            critical_patterns = [
                '*.db',  # Файлы базы данных
                '*.sqlite*',  # SQLite файлы
                'settings.py',  # Файлы настроек
                '*.env',  # Файлы окружения
            ]
            
            for pattern in critical_patterns:
                if list(path.rglob(pattern)):
                    return True
            
            return False
            
        except Exception:
            # В случае ошибки считаем, что файлы критические (безопасный подход)
            return True


class FileUploadHandler:
    """
    Обработчик загрузки файлов.
    
    Компонент для обработки загрузки файлов с валидацией,
    созданием необходимых папок и безопасным сохранением.
    """
    
    # Разрешенные типы файлов для изображений
    ALLOWED_IMAGE_TYPES = [
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
    ]
    
    # Разрешенные типы файлов для документов
    ALLOWED_DOCUMENT_TYPES = [
        'application/pdf', 'text/plain', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/csv', 'application/json'
    ]
    
    # Максимальные размеры файлов (в байтах)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    def validate_file(file: UploadedFile, allowed_types: list, max_size: int, 
                     user_id: Optional[int] = None) -> bool:
        """
        Расширенная валидация загружаемого файла (устаревший метод).
        
        Рекомендуется использовать FileValidationSystem.validate_file_type()
        для более комплексной валидации.
        
        Args:
            file: Загружаемый файл
            allowed_types: Список разрешенных MIME типов
            max_size: Максимальный размер файла в байтах
            user_id: ID пользователя для логирования
            
        Returns:
            bool: True если файл прошел валидацию
            
        Raises:
            FileUploadError: Если файл не прошел валидацию
        """
        try:
            # Проверка наличия файла
            if not file or not hasattr(file, 'size') or not hasattr(file, 'content_type'):
                raise FileUploadError(
                    "Invalid file object",
                    file_size=0,
                    file_type="unknown",
                    user_id=user_id
                )
            
            # Проверка размера файла
            if file.size <= 0:
                raise FileUploadError(
                    "File is empty",
                    file_size=file.size,
                    file_type=file.content_type,
                    user_id=user_id
                )
            
            if file.size > max_size:
                raise FileUploadError(
                    f"File size {file.size} exceeds maximum allowed size {max_size}",
                    file_size=file.size,
                    file_type=file.content_type,
                    user_id=user_id
                )
            
            # Проверка типа файла
            if file.content_type not in allowed_types:
                raise FileUploadError(
                    f"File type {file.content_type} is not allowed. Allowed types: {', '.join(allowed_types)}",
                    file_size=file.size,
                    file_type=file.content_type,
                    user_id=user_id
                )
            
            # Проверка имени файла
            if hasattr(file, 'name') and file.name:
                if not FilePathValidator.validate_filename(file.name):
                    raise FileUploadError(
                        f"Invalid filename: {file.name}",
                        file_size=file.size,
                        file_type=file.content_type,
                        user_id=user_id
                    )
            
            # Дополнительные проверки безопасности
            FileUploadHandler._perform_security_checks(file, user_id)
            
            return True
            
        except FileUploadError:
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = FileUploadError(
                f"Unexpected error during file validation: {e}",
                file_size=getattr(file, 'size', 0),
                file_type=getattr(file, 'content_type', 'unknown'),
                user_id=user_id,
                original_error=e
            )
            FileOperationLogger.log_error("validate_file", error, user_id=user_id)
            raise error
    
    @staticmethod
    def validate_file_comprehensive(file: UploadedFile, file_type: str, user, 
                                  target_object=None, current_file_count: int = 0) -> Dict[str, Any]:
        """
        Комплексная валидация файла с использованием новой системы валидации.
        
        Args:
            file: Загружаемый файл
            file_type: Тип файла ('avatar', 'project_image', 'project_document', 'glossary_file')
            user: Объект пользователя
            target_object: Целевой объект (проект для файлов проекта)
            current_file_count: Текущее количество файлов данного типа
            
        Returns:
            Dict[str, Any]: Результат валидации с деталями
            
        Raises:
            FileUploadError: При критических ошибках валидации
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'file_info': {},
            'checks_performed': []
        }
        
        try:
            user_id = getattr(user, 'id', None)
            
            # 1. Валидация типа файла
            type_validation = FileValidationSystem.validate_file_type(file, file_type, user_id)
            validation_results['checks_performed'].append('file_type_validation')
            validation_results['file_info'] = type_validation['file_info']
            
            if not type_validation['valid']:
                validation_results['valid'] = False
                validation_results['errors'].extend(type_validation['errors'])
            
            validation_results['warnings'].extend(type_validation['warnings'])
            
            # 2. Проверка прав доступа
            permission_check = FileValidationSystem.check_user_permissions(user, file_type, target_object)
            validation_results['checks_performed'].append('permission_check')
            
            if not permission_check['valid']:
                validation_results['valid'] = False
                validation_results['errors'].extend(permission_check['errors'])
            
            validation_results['warnings'].extend(permission_check['warnings'])
            
            # 3. Проверка ограничений на количество файлов
            count_check = FileValidationSystem.check_file_count_limits(file_type, current_file_count, user_id)
            validation_results['checks_performed'].append('file_count_limits')
            
            if not count_check['valid']:
                validation_results['valid'] = False
                validation_results['errors'].extend(count_check['errors'])
            
            validation_results['warnings'].extend(count_check['warnings'])
            
            # 4. Проверка ограничений дискового пространства
            team_id = None
            project_id = None
            
            if target_object and hasattr(target_object, 'team'):
                team_id = target_object.team.id
                project_id = target_object.id
            
            storage_check = FileValidationSystem.check_storage_limits(
                user_id, team_id, project_id, getattr(file, 'size', 0)
            )
            validation_results['checks_performed'].append('storage_limits')
            
            if not storage_check['valid']:
                validation_results['valid'] = False
                validation_results['errors'].extend(storage_check['errors'])
            
            validation_results['warnings'].extend(storage_check['warnings'])
            
            # Логируем результат комплексной валидации
            if validation_results['valid']:
                FileOperationLogger.log_file_uploaded(
                    getattr(file, 'name', 'unknown'),
                    user_id,
                    getattr(file, 'size', 0),
                    getattr(file, 'content_type', 'unknown'),
                    f"comprehensive_validation_passed_{file_type}"
                )
            else:
                FileOperationLogger.log_error(
                    "comprehensive_validation_failed",
                    FileValidationError(
                        f"Comprehensive validation failed: {'; '.join(validation_results['errors'])}",
                        filename=getattr(file, 'name', 'unknown'),
                        validation_type=file_type
                    ),
                    user_id=user_id
                )
            
            return validation_results
            
        except Exception as e:
            error = FileUploadError(
                f"Error during comprehensive file validation: {e}",
                file_size=getattr(file, 'size', 0),
                file_type=getattr(file, 'content_type', 'unknown'),
                user_id=getattr(user, 'id', None),
                original_error=e
            )
            FileOperationLogger.log_error("validate_file_comprehensive", error, user_id=getattr(user, 'id', None))
            raise error
    
    @staticmethod
    def _perform_security_checks(file: UploadedFile, user_id: Optional[int] = None):
        """
        Выполнить дополнительные проверки безопасности файла.
        
        Args:
            file: Загружаемый файл
            user_id: ID пользователя для логирования
            
        Raises:
            FileSecurityError: При обнаружении угроз безопасности
        """
        try:
            # Проверяем расширение файла
            if hasattr(file, 'name') and file.name:
                name_lower = file.name.lower()
                
                # Опасные расширения
                dangerous_extensions = [
                    '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
                    '.jar', '.php', '.asp', '.aspx', '.jsp', '.py', '.pl', '.sh'
                ]
                
                if any(name_lower.endswith(ext) for ext in dangerous_extensions):
                    raise FileSecurityError(
                        f"Dangerous file extension detected: {file.name}",
                        path=file.name,
                        user_id=user_id
                    )
            
            # Проверяем содержимое файла на наличие подозрительных паттернов
            if hasattr(file, 'read'):
                # Сохраняем текущую позицию
                current_pos = file.tell() if hasattr(file, 'tell') else 0
                
                try:
                    # Читаем первые 1024 байта для анализа
                    file.seek(0)
                    content_sample = file.read(1024)
                    
                    # Проверяем на наличие исполняемых заголовков
                    if content_sample.startswith(b'MZ') or content_sample.startswith(b'\x7fELF'):
                        raise FileSecurityError(
                            f"Executable file detected: {getattr(file, 'name', 'unknown')}",
                            path=getattr(file, 'name', 'unknown'),
                            user_id=user_id
                        )
                    
                finally:
                    # Возвращаем файл в исходную позицию
                    if hasattr(file, 'seek'):
                        file.seek(current_pos)
                        
        except FileSecurityError:
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            # Логируем ошибку, но не блокируем загрузку
            FileOperationLogger.log_error("security_check", e, user_id=user_id)
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        Очистить имя файла от недопустимых символов.
        
        Args:
            filename: Исходное имя файла
            
        Returns:
            str: Очищенное имя файла
        """
        return FilePathValidator.sanitize_filename_advanced(filename)
    
    @staticmethod
    def handle_avatar_upload(user, file: UploadedFile, use_comprehensive_validation: bool = True) -> str:
        """
        Обработать загрузку аватарки пользователя с расширенной обработкой ошибок.
        
        Args:
            user: Объект пользователя
            file: Загружаемый файл
            use_comprehensive_validation: Использовать комплексную валидацию
            
        Returns:
            str: Путь к сохраненному файлу
            
        Raises:
            FileUploadError: Если загрузка не удалась
        """
        try:
            # Комплексная валидация файла
            if use_comprehensive_validation:
                validation_result = FileUploadHandler.validate_file_comprehensive(
                    file, 'avatar', user, current_file_count=1 if user.avatar else 0
                )
                
                if not validation_result['valid']:
                    raise FileUploadError(
                        f"Avatar validation failed: {'; '.join(validation_result['errors'])}",
                        file_size=getattr(file, 'size', 0),
                        file_type=getattr(file, 'content_type', 'unknown'),
                        user_id=user.id
                    )
                
                # Логируем предупреждения если есть
                if validation_result['warnings']:
                    FileOperationLogger.log_error(
                        "avatar_upload_warnings",
                        FileUploadError(f"Avatar upload warnings: {'; '.join(validation_result['warnings'])}"),
                        user_id=user.id
                    )
            else:
                # Старая валидация для обратной совместимости
                FileUploadHandler.validate_file(
                    file, 
                    FileUploadHandler.ALLOWED_IMAGE_TYPES,
                    FileUploadHandler.MAX_IMAGE_SIZE,
                    user.id
                )
            
            # Создаем папку пользователя если не существует
            DirectoryManager.create_user_directory(user.id)
            
            # Генерируем путь для сохранения
            file_path = FilePathManager.get_avatar_path(user.id)
            
            # Удаляем старую аватарку если существует
            if user.avatar:
                old_path = Path(settings.MEDIA_ROOT) / str(user.avatar)
                if old_path.exists():
                    try:
                        old_path.unlink()
                        FileOperationLogger.log_file_deleted(old_path, user.id, "avatar_replacement")
                    except Exception as e:
                        # Логируем ошибку удаления старого файла, но продолжаем
                        FileOperationLogger.log_error("delete_old_avatar", e, old_path, user.id)
            
            FileOperationLogger.log_file_uploaded(
                file_path, 
                user.id, 
                file.size, 
                file.content_type,
                "avatar_upload"
            )
            return file_path
            
        except (FileUploadError, FileSecurityError, DirectoryCreationError, FileValidationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = FileUploadError(
                f"Failed to upload avatar for user {user.id}",
                file_size=getattr(file, 'size', 0),
                file_type=getattr(file, 'content_type', 'unknown'),
                user_id=user.id,
                original_error=e
            )
            FileOperationLogger.log_error("handle_avatar_upload", error, user_id=user.id, notify_admins=True)
            raise error
    
    @staticmethod
    def handle_project_image_upload(project, file: UploadedFile, user, 
                                   current_file_count: int = 0, use_comprehensive_validation: bool = True) -> str:
        """
        Обработать загрузку изображения проекта с расширенной обработкой ошибок.
        
        Args:
            project: Объект проекта
            file: Загружаемый файл
            user: Объект пользователя, загружающего файл
            current_file_count: Текущее количество изображений в проекте
            use_comprehensive_validation: Использовать комплексную валидацию
            
        Returns:
            str: Путь к сохраненному файлу
            
        Raises:
            FileUploadError: Если загрузка не удалась
        """
        try:
            user_id = getattr(user, 'id', None)
            
            # Комплексная валидация файла
            if use_comprehensive_validation:
                validation_result = FileUploadHandler.validate_file_comprehensive(
                    file, 'project_image', user, project, current_file_count
                )
                
                if not validation_result['valid']:
                    raise FileUploadError(
                        f"Project image validation failed: {'; '.join(validation_result['errors'])}",
                        file_size=getattr(file, 'size', 0),
                        file_type=getattr(file, 'content_type', 'unknown'),
                        user_id=user_id
                    )
                
                # Логируем предупреждения если есть
                if validation_result['warnings']:
                    FileOperationLogger.log_error(
                        "project_image_upload_warnings",
                        FileUploadError(f"Project image upload warnings: {'; '.join(validation_result['warnings'])}"),
                        user_id=user_id
                    )
            else:
                # Старая валидация для обратной совместимости
                FileUploadHandler.validate_file(
                    file,
                    FileUploadHandler.ALLOWED_IMAGE_TYPES,
                    FileUploadHandler.MAX_IMAGE_SIZE,
                    user_id
                )
            
            # Создаем папку проекта если не существует
            DirectoryManager.create_project_directory(project.team.id, project.content_folder)
            
            # Очищаем имя файла
            clean_name = FileUploadHandler.clean_filename(file.name)
            
            # Генерируем путь для сохранения
            file_path = FilePathManager.get_project_image_path(
                project.team.id, 
                project.content_folder, 
                clean_name
            )
            
            FileOperationLogger.log_file_uploaded(
                file_path, 
                user_id, 
                file.size,
                file.content_type,
                "project_image_upload"
            )
            return file_path
            
        except (FileUploadError, FileSecurityError, DirectoryCreationError, FileValidationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = FileUploadError(
                f"Failed to upload image for project {project.id}",
                file_size=getattr(file, 'size', 0),
                file_type=getattr(file, 'content_type', 'unknown'),
                user_id=getattr(user, 'id', None),
                original_error=e
            )
            FileOperationLogger.log_error("handle_project_image_upload", error, user_id=getattr(user, 'id', None), notify_admins=True)
            raise error
    
    @staticmethod
    def handle_document_upload(project, file: UploadedFile, document_type: str, user,
                              current_file_count: int = 0, use_comprehensive_validation: bool = True) -> str:
        """
        Обработать загрузку документа проекта с расширенной обработкой ошибок.
        
        Args:
            project: Объект проекта
            file: Загружаемый файл
            document_type: Тип документа ('documents' или 'glossary')
            user: Объект пользователя, загружающего файл
            current_file_count: Текущее количество документов данного типа в проекте
            use_comprehensive_validation: Использовать комплексную валидацию
            
        Returns:
            str: Путь к сохраненному файлу
            
        Raises:
            FileUploadError: Если загрузка не удалась
        """
        try:
            user_id = getattr(user, 'id', None)
            
            # Валидация типа документа
            allowed_document_types = ['documents', 'glossary']
            if document_type not in allowed_document_types:
                raise FileUploadError(
                    f"Invalid document type: {document_type}. Allowed types: {', '.join(allowed_document_types)}",
                    file_size=getattr(file, 'size', 0),
                    file_type=getattr(file, 'content_type', 'unknown'),
                    user_id=user_id
                )
            
            # Определяем тип файла для валидации
            validation_file_type = 'glossary_file' if document_type == 'glossary' else 'project_document'
            
            # Комплексная валидация файла
            if use_comprehensive_validation:
                validation_result = FileUploadHandler.validate_file_comprehensive(
                    file, validation_file_type, user, project, current_file_count
                )
                
                if not validation_result['valid']:
                    raise FileUploadError(
                        f"Document validation failed: {'; '.join(validation_result['errors'])}",
                        file_size=getattr(file, 'size', 0),
                        file_type=getattr(file, 'content_type', 'unknown'),
                        user_id=user_id
                    )
                
                # Логируем предупреждения если есть
                if validation_result['warnings']:
                    FileOperationLogger.log_error(
                        "document_upload_warnings",
                        FileUploadError(f"Document upload warnings: {'; '.join(validation_result['warnings'])}"),
                        user_id=user_id
                    )
            else:
                # Старая валидация для обратной совместимости
                FileUploadHandler.validate_file(
                    file,
                    FileUploadHandler.ALLOWED_DOCUMENT_TYPES,
                    FileUploadHandler.MAX_DOCUMENT_SIZE,
                    user_id
                )
            
            # Создаем папку проекта если не существует
            DirectoryManager.create_project_directory(project.team.id, project.content_folder)
            
            # Очищаем имя файла
            clean_name = FileUploadHandler.clean_filename(file.name)
            
            # Генерируем путь для сохранения в зависимости от типа документа
            if document_type == 'glossary':
                file_path = FilePathManager.get_project_glossary_path(
                    project.team.id,
                    project.content_folder,
                    clean_name
                )
            else:
                file_path = FilePathManager.get_project_document_path(
                    project.team.id,
                    project.content_folder,
                    clean_name
                )
            
            FileOperationLogger.log_file_uploaded(
                file_path, 
                user_id, 
                file.size,
                file.content_type,
                f"{document_type}_upload"
            )
            return file_path
            
        except (FileUploadError, FileSecurityError, DirectoryCreationError, FileValidationError):
            # Перебрасываем наши исключения как есть
            raise
        except Exception as e:
            error = FileUploadError(
                f"Failed to upload {document_type} document for project {project.id}",
                file_size=getattr(file, 'size', 0),
                file_type=getattr(file, 'content_type', 'unknown'),
                user_id=getattr(user, 'id', None),
                original_error=e
            )
            FileOperationLogger.log_error("handle_document_upload", error, user_id=getattr(user, 'id', None), notify_admins=True)
            raise error


class FileCleanupManager:
    """
    Менеджер очистки файлов.
    
    Компонент для безопасного удаления файлов и папок при удалении
    объектов из системы с соответствующим логированием.
    """
    
    @staticmethod
    def cleanup_user_files(user_id: int) -> bool:
        """
        Очистить файлы пользователя с расширенной обработкой ошибок.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            bool: True если очистка прошла успешно
            
        Raises:
            FileCleanupError: При критических ошибках очистки
        """
        try:
            user_path = FilePathManager.get_user_path(user_id)
            
            # Проверяем, существует ли папка
            if not user_path.exists():
                FileOperationLogger.log_file_deleted(user_path, user_id, "cleanup_user_files_not_found")
                return True
            
            # Безопасно удаляем папку
            success = DirectoryManager.remove_directory_safe(user_path, user_id)
            
            if success:
                FileOperationLogger.log_file_deleted(user_path, user_id, "cleanup_user_files_success")
            else:
                error = FileCleanupError(
                    f"Failed to remove user directory: {user_path}",
                    path=user_path,
                    cleanup_type="user_cleanup"
                )
                FileOperationLogger.log_error("cleanup_user_files", error, user_path, user_id, notify_admins=True)
            
            return success
            
        except Exception as e:
            error = FileCleanupError(
                f"Failed to cleanup files for user {user_id}",
                path=FilePathManager.get_user_path(user_id),
                original_error=e,
                cleanup_type="user_cleanup"
            )
            FileOperationLogger.log_error("cleanup_user_files", error, user_id=user_id, notify_admins=True)
            raise error
    
    @staticmethod
    def cleanup_project_files(team_id: int, content_folder: str) -> bool:
        """
        Очистить файлы проекта с расширенной обработкой ошибок.
        
        Args:
            team_id: ID команды
            content_folder: Имя папки контента проекта
            
        Returns:
            bool: True если очистка прошла успешно
            
        Raises:
            FileCleanupError: При критических ошибках очистки
        """
        try:
            project_path = FilePathManager.get_project_path(team_id, content_folder)
            
            # Проверяем, существует ли папка
            if not project_path.exists():
                FileOperationLogger.log_file_deleted(project_path, operation_context="cleanup_project_files_not_found")
                return True
            
            # Безопасно удаляем папку
            success = DirectoryManager.remove_directory_safe(project_path)
            
            if success:
                FileOperationLogger.log_file_deleted(project_path, operation_context="cleanup_project_files_success")
            else:
                error = FileCleanupError(
                    f"Failed to remove project directory: {project_path}",
                    path=project_path,
                    cleanup_type="project_cleanup"
                )
                FileOperationLogger.log_error("cleanup_project_files", error, project_path, notify_admins=True)
            
            return success
            
        except Exception as e:
            error = FileCleanupError(
                f"Failed to cleanup files for project {content_folder}",
                path=FilePathManager.get_project_path(team_id, content_folder),
                original_error=e,
                cleanup_type="project_cleanup"
            )
            FileOperationLogger.log_error("cleanup_project_files", error, notify_admins=True)
            raise error
    
    @staticmethod
    def cleanup_team_files(team_id: int) -> bool:
        """
        Очистить файлы команды с расширенной обработкой ошибок.
        
        Args:
            team_id: ID команды
            
        Returns:
            bool: True если очистка прошла успешно
            
        Raises:
            FileCleanupError: При критических ошибках очистки
        """
        try:
            team_path = FilePathManager.get_team_path(team_id)
            
            # Проверяем, существует ли папка
            if not team_path.exists():
                FileOperationLogger.log_file_deleted(team_path, operation_context="cleanup_team_files_not_found")
                return True
            
            # Безопасно удаляем папку
            success = DirectoryManager.remove_directory_safe(team_path)
            
            if success:
                FileOperationLogger.log_file_deleted(team_path, operation_context="cleanup_team_files_success")
            else:
                error = FileCleanupError(
                    f"Failed to remove team directory: {team_path}",
                    path=team_path,
                    cleanup_type="team_cleanup"
                )
                FileOperationLogger.log_error("cleanup_team_files", error, team_path, notify_admins=True)
            
            return success
            
        except Exception as e:
            error = FileCleanupError(
                f"Failed to cleanup files for team {team_id}",
                path=FilePathManager.get_team_path(team_id),
                original_error=e,
                cleanup_type="team_cleanup"
            )
            FileOperationLogger.log_error("cleanup_team_files", error, notify_admins=True)
            raise error
    
    @staticmethod
    def cleanup_orphaned_files() -> int:
        """
        Очистить файлы без связанных объектов.
        
        Returns:
            int: Количество удаленных файлов
            
        Note:
            Эта функция будет реализована позже с использованием моделей Django
            для проверки существования связанных объектов
        """
        try:
            # TODO: Реализовать после создания моделей
            FileOperationLogger.log_error("cleanup_orphaned_files", 
                                         Exception("Not implemented yet - requires Django models"))
            return 0
            
        except Exception as e:
            error = FileCleanupError(
                "Failed to cleanup orphaned files",
                original_error=e,
                cleanup_type="orphaned_cleanup"
            )
            FileOperationLogger.log_error("cleanup_orphaned_files", error, notify_admins=True)
            raise error


class FileSystemMonitor:
    """
    Монитор файловой системы для отслеживания состояния и производительности.
    """
    
    @staticmethod
    def get_disk_usage(path: Union[str, Path] = None) -> Dict[str, int]:
        """
        Получить информацию об использовании диска.
        
        Args:
            path: Путь для проверки (по умолчанию MEDIA_ROOT)
            
        Returns:
            Dict[str, int]: Словарь с информацией о диске
        """
        try:
            if path is None:
                path = settings.MEDIA_ROOT
            
            path = Path(path)
            stat = shutil.disk_usage(path)
            
            return {
                'total': stat.total,
                'used': stat.total - stat.free,
                'free': stat.free,
                'percent_used': round((stat.total - stat.free) / stat.total * 100, 2)
            }
            
        except Exception as e:
            FileOperationLogger.log_error("get_disk_usage", e, path)
            return {'total': 0, 'used': 0, 'free': 0, 'percent_used': 0}
    
    @staticmethod
    def get_directory_size(path: Union[str, Path]) -> int:
        """
        Получить размер папки в байтах.
        
        Args:
            path: Путь к папке
            
        Returns:
            int: Размер папки в байтах
        """
        try:
            path = Path(path)
            if not path.exists():
                return 0
            
            total_size = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                    except (OSError, FileNotFoundError):
                        # Файл мог быть удален между проверками
                        continue
            
            return total_size
            
        except Exception as e:
            FileOperationLogger.log_error("get_directory_size", e, path)
            return 0
    
    @staticmethod
    def get_file_count(path: Union[str, Path]) -> Dict[str, int]:
        """
        Получить количество файлов в папке.
        
        Args:
            path: Путь к папке
            
        Returns:
            Dict[str, int]: Словарь с количеством файлов и папок
        """
        try:
            path = Path(path)
            if not path.exists():
                return {'files': 0, 'directories': 0}
            
            file_count = 0
            dir_count = 0
            
            for item in path.rglob('*'):
                try:
                    if item.is_file():
                        file_count += 1
                    elif item.is_dir():
                        dir_count += 1
                except (OSError, FileNotFoundError):
                    # Файл мог быть удален между проверками
                    continue
            
            return {'files': file_count, 'directories': dir_count}
            
        except Exception as e:
            FileOperationLogger.log_error("get_file_count", e, path)
            return {'files': 0, 'directories': 0}
    
    @staticmethod
    def check_system_health() -> Dict[str, Any]:
        """
        Проверить общее состояние файловой системы.
        
        Returns:
            Dict[str, Any]: Отчет о состоянии системы
        """
        try:
            media_root = Path(settings.MEDIA_ROOT)
            
            # Проверяем основные папки
            users_path = media_root / 'users'
            teams_path = media_root / 'teams'
            temp_path = media_root / 'temp'
            
            health_report = {
                'timestamp': timezone.now().isoformat(),
                'disk_usage': FileSystemMonitor.get_disk_usage(),
                'directories': {
                    'users': {
                        'exists': users_path.exists(),
                        'size': FileSystemMonitor.get_directory_size(users_path),
                        'file_count': FileSystemMonitor.get_file_count(users_path)
                    },
                    'teams': {
                        'exists': teams_path.exists(),
                        'size': FileSystemMonitor.get_directory_size(teams_path),
                        'file_count': FileSystemMonitor.get_file_count(teams_path)
                    },
                    'temp': {
                        'exists': temp_path.exists(),
                        'size': FileSystemMonitor.get_directory_size(temp_path),
                        'file_count': FileSystemMonitor.get_file_count(temp_path)
                    }
                },
                'warnings': []
            }
            
            # Проверяем на предупреждения
            disk_usage = health_report['disk_usage']
            if disk_usage['percent_used'] > 90:
                health_report['warnings'].append('Disk usage is critically high (>90%)')
            elif disk_usage['percent_used'] > 80:
                health_report['warnings'].append('Disk usage is high (>80%)')
            
            # Проверяем размер временной папки
            temp_size = health_report['directories']['temp']['size']
            if temp_size > 100 * 1024 * 1024:  # 100MB
                health_report['warnings'].append('Temporary directory is large (>100MB)')
            
            return health_report
            
        except Exception as e:
            FileOperationLogger.log_error("check_system_health", e, notify_admins=True)
            return {
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'warnings': ['System health check failed']
            }


# Upload_to функции для Django моделей
def user_avatar_upload_path(instance, filename):
    """
    Функция upload_to для аватарок пользователей с расширенной обработкой ошибок.
    
    Args:
        instance: Экземпляр модели User
        filename: Исходное имя файла
        
    Returns:
        str: Путь для сохранения файла
    """
    try:
        # Создаем папку пользователя если не существует
        DirectoryManager.create_user_directory(instance.id)
        
        # Всегда сохраняем аватарку как avatar.jpg независимо от исходного имени
        file_path = FilePathManager.get_avatar_path(instance.id)
        
        # Проверяем безопасность пути
        if not FilePathValidator.validate_path_security(file_path):
            FileOperationLogger.log_security_violation(
                "unsafe_avatar_upload_path",
                file_path,
                user_id=instance.id,
                details=f"Unsafe upload path detected: {file_path}"
            )
            raise FileSecurityError(f"Unsafe upload path: {file_path}", path=file_path, user_id=instance.id)
        
        return file_path
        
    except (FileSecurityError, DirectoryCreationError):
        # Перебрасываем наши исключения как есть
        raise
    except Exception as e:
        error = FileUploadError(
            f"Error generating avatar upload path for user {instance.id}",
            user_id=instance.id,
            original_error=e
        )
        FileOperationLogger.log_error("user_avatar_upload_path", error, user_id=instance.id)
        # Возвращаем безопасный fallback путь
        return f"users/{instance.id}/avatar.jpg"


def project_image_upload_path(instance, filename):
    """
    Функция upload_to для изображений проектов с расширенной обработкой ошибок.
    
    Args:
        instance: Экземпляр модели с полем project (например, ImageContent)
        filename: Исходное имя файла
        
    Returns:
        str: Путь для сохранения файла
    """
    try:
        # Очищаем имя файла от недопустимых символов
        clean_name = FilePathValidator.sanitize_filename(filename)
        
        # Получаем данные проекта
        project = instance.project
        team_id = project.team.id
        content_folder = project.content_folder
        
        # Создаем папку проекта если не существует
        DirectoryManager.create_project_directory(team_id, content_folder)
        
        file_path = FilePathManager.get_project_image_path(team_id, content_folder, clean_name)
        
        # Проверяем безопасность пути
        if not FilePathValidator.validate_path_security(file_path):
            FileOperationLogger.log_security_violation(
                "unsafe_project_image_upload_path",
                file_path,
                details=f"Unsafe upload path detected: {file_path}"
            )
            raise FileSecurityError(f"Unsafe upload path: {file_path}", path=file_path)
        
        return file_path
        
    except (FileSecurityError, DirectoryCreationError, FileValidationError):
        # Перебрасываем наши исключения как есть
        raise
    except Exception as e:
        error = FileUploadError(
            f"Error generating project image upload path",
            original_error=e
        )
        FileOperationLogger.log_error("project_image_upload_path", error)
        # Возвращаем безопасный fallback путь
        clean_name = FilePathValidator.sanitize_filename(filename)
        return f"teams/{instance.project.team.id}/projects/{instance.project.content_folder}/images/{clean_name}"


def project_document_upload_path(instance, filename):
    """
    Функция upload_to для документов проектов с расширенной обработкой ошибок.
    
    Args:
        instance: Экземпляр модели с полем project (например, ProjectDocument)
        filename: Исходное имя файла
        
    Returns:
        str: Путь для сохранения файла
    """
    try:
        # Очищаем имя файла от недопустимых символов
        clean_name = FilePathValidator.sanitize_filename(filename)
        
        # Получаем данные проекта
        project = instance.project
        team_id = project.team.id
        content_folder = project.content_folder
        
        # Создаем папку проекта если не существует
        DirectoryManager.create_project_directory(team_id, content_folder)
        
        # Определяем тип документа для выбора подпапки
        document_type = getattr(instance, 'document_type', 'documents')
        
        if document_type == 'glossary':
            file_path = FilePathManager.get_project_glossary_path(team_id, content_folder, clean_name)
        else:
            file_path = FilePathManager.get_project_document_path(team_id, content_folder, clean_name)
        
        # Проверяем безопасность пути
        if not FilePathValidator.validate_path_security(file_path):
            FileOperationLogger.log_security_violation(
                "unsafe_project_document_upload_path",
                file_path,
                details=f"Unsafe upload path detected: {file_path}"
            )
            raise FileSecurityError(f"Unsafe upload path: {file_path}", path=file_path)
        
        return file_path
        
    except (FileSecurityError, DirectoryCreationError, FileValidationError):
        # Перебрасываем наши исключения как есть
        raise
    except Exception as e:
        error = FileUploadError(
            f"Error generating project document upload path",
            original_error=e
        )
        FileOperationLogger.log_error("project_document_upload_path", error)
        # Возвращаем безопасный fallback путь
        clean_name = FilePathValidator.sanitize_filename(filename)
        if getattr(instance, 'document_type', 'documents') == 'glossary':
            return f"teams/{instance.project.team.id}/projects/{instance.project.content_folder}/glossary/{clean_name}"
        else:
            return f"teams/{instance.project.team.id}/projects/{instance.project.content_folder}/documents/{clean_name}"


class FilePathValidator:
    """
    Валидатор путей и имен файлов.
    
    Класс для валидации путей к файлам и очистки имен файлов
    от потенциально опасных символов и конструкций.
    """
    
    # Недопустимые символы в именах файлов
    INVALID_CHARS = '<>:"/\\|?*'
    
    # Недопустимые имена файлов в Windows
    INVALID_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    # Максимальная длина имени файла
    MAX_FILENAME_LENGTH = 255
    MAX_NAME_PART_LENGTH = 100
    
    # Дополнительные недопустимые символы для безопасности
    SECURITY_INVALID_CHARS = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    
    # Подозрительные расширения файлов
    SUSPICIOUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
        '.php', '.asp', '.aspx', '.jsp', '.py', '.pl', '.sh', '.ps1', '.vb'
    }
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """
        Проверить валидность имени файла.
        
        Args:
            filename: Имя файла для проверки
            
        Returns:
            bool: True если имя файла валидно
        """
        if not filename or len(filename) > FilePathValidator.MAX_FILENAME_LENGTH:
            return False
        
        # Проверяем на недопустимые символы
        if any(char in filename for char in FilePathValidator.INVALID_CHARS):
            return False
        
        # Проверяем на недопустимые имена Windows
        name_part = os.path.splitext(filename)[0].upper()
        if name_part in FilePathValidator.INVALID_NAMES:
            return False
        
        # Проверяем, что файл не начинается с точки (скрытые файлы)
        if filename.startswith('.'):
            return False
        
        return True
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Очистить имя файла от недопустимых символов.
        
        Args:
            filename: Исходное имя файла
            
        Returns:
            str: Очищенное имя файла
        """
        if not filename:
            return "unnamed_file"
        
        # Удаляем недопустимые символы
        for char in FilePathValidator.INVALID_CHARS:
            filename = filename.replace(char, '_')
        
        # Разделяем имя и расширение
        name, ext = os.path.splitext(filename)
        
        # Проверяем на недопустимые имена Windows
        if name.upper() in FilePathValidator.INVALID_NAMES:
            name = f"{name}_file"
        
        # Ограничиваем длину имени файла
        if len(name) > FilePathValidator.MAX_NAME_PART_LENGTH:
            name = name[:FilePathValidator.MAX_NAME_PART_LENGTH]
        
        # Убираем точки в начале и конце
        name = name.strip('.')
        
        # Если имя стало пустым, даем дефолтное
        if not name:
            name = "unnamed_file"
        
        return f"{name}{ext}"
    
    @staticmethod
    def validate_path_security(file_path: str) -> bool:
        """
        Проверить безопасность пути к файлу (защита от path traversal).
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            bool: True если путь безопасен
        """
        # Проверяем на попытки выхода за пределы разрешенных папок до нормализации
        if '..' in file_path or file_path.startswith('/'):
            return False
        
        # Нормализуем путь и заменяем обратные слеши на прямые
        normalized_path = os.path.normpath(file_path).replace('\\', '/')
        
        # Проверяем, что путь начинается с разрешенных префиксов
        allowed_prefixes = ['users/', 'teams/', 'temp/']
        if not any(normalized_path.startswith(prefix) for prefix in allowed_prefixes):
            return False
        
        return True
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: list = None) -> bool:
        """
        Проверить расширение файла на соответствие разрешенным типам.
        
        Args:
            filename: Имя файла
            allowed_extensions: Список разрешенных расширений (с точкой)
            
        Returns:
            bool: True если расширение разрешено
        """
        if not filename:
            return False
        
        _, ext = os.path.splitext(filename.lower())
        
        # Проверяем на подозрительные расширения
        if ext in FilePathValidator.SUSPICIOUS_EXTENSIONS:
            return False
        
        # Если указаны разрешенные расширения, проверяем соответствие
        if allowed_extensions:
            return ext in [e.lower() for e in allowed_extensions]
        
        return True
    
    @staticmethod
    def validate_filename_security(filename: str) -> bool:
        """
        Расширенная проверка безопасности имени файла.
        
        Args:
            filename: Имя файла для проверки
            
        Returns:
            bool: True если имя файла безопасно
        """
        if not filename:
            return False
        
        # Проверяем на управляющие символы
        if any(char in filename for char in FilePathValidator.SECURITY_INVALID_CHARS):
            return False
        
        # Проверяем на попытки обхода пути
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            return False
        
        # Проверяем на двойные расширения (потенциально опасно)
        parts = filename.split('.')
        if len(parts) > 3:  # имя.расширение1.расширение2 - подозрительно
            return False
        
        # Проверяем на слишком длинные имена
        if len(filename) > FilePathValidator.MAX_FILENAME_LENGTH:
            return False
        
        return True
    
    @staticmethod
    def sanitize_filename_advanced(filename: str) -> str:
        """
        Расширенная очистка имени файла с дополнительными проверками безопасности.
        
        Args:
            filename: Исходное имя файла
            
        Returns:
            str: Очищенное и безопасное имя файла
        """
        if not filename:
            return "unnamed_file"
        
        # Удаляем управляющие символы
        for char in FilePathValidator.SECURITY_INVALID_CHARS:
            filename = filename.replace(char, '')
        
        # Базовая очистка
        filename = FilePathValidator.sanitize_filename(filename)
        
        # Дополнительная проверка на двойные расширения
        parts = filename.split('.')
        if len(parts) > 3:
            # Оставляем только имя и последнее расширение
            name = '.'.join(parts[:-1]).replace('.', '_')
            ext = parts[-1]
            filename = f"{name}.{ext}"
        
        # Убираем пробелы в начале и конце
        filename = filename.strip()
        
        # Заменяем множественные пробелы одним
        import re
        filename = re.sub(r'\s+', ' ', filename)
        
        return filename
    
    @staticmethod
    def get_safe_upload_path(base_path: str, filename: str) -> str:
        """
        Получить безопасный путь для загрузки файла.
        
        Args:
            base_path: Базовый путь
            filename: Имя файла
            
        Returns:
            str: Безопасный путь для загрузки
            
        Raises:
            FileUploadError: Если путь небезопасен
        """
        # Расширенная очистка имени файла
        safe_filename = FilePathValidator.sanitize_filename_advanced(filename)
        
        # Формируем полный путь
        full_path = os.path.join(base_path, safe_filename)
        
        # Проверяем безопасность пути
        if not FilePathValidator.validate_path_security(full_path):
            raise FileUploadError(f"Unsafe file path: {full_path}")
        
        return full_path


class FileValidationSystem:
    """
    Комплексная система валидации и ограничений для файлов.
    
    Обеспечивает валидацию типов файлов, размеров, количества файлов
    и проверки прав доступа при загрузке.
    """
    
    # Конфигурация ограничений по типам файлов
    FILE_TYPE_CONFIGS = {
        'avatar': {
            'allowed_types': ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
            'allowed_extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'max_size': 5 * 1024 * 1024,  # 5MB
            'max_count_per_user': 1,
            'description': 'Аватарка пользователя'
        },
        'project_image': {
            'allowed_types': ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'],
            'allowed_extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'max_size': 10 * 1024 * 1024,  # 10MB
            'max_count_per_project': 50,
            'description': 'Изображение проекта'
        },
        'project_document': {
            'allowed_types': [
                'application/pdf', 'text/plain', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/csv', 'application/json', 'text/markdown'
            ],
            'allowed_extensions': ['.pdf', '.txt', '.doc', '.docx', '.csv', '.json', '.md'],
            'max_size': 25 * 1024 * 1024,  # 25MB
            'max_count_per_project': 100,
            'description': 'Документ проекта'
        },
        'glossary_file': {
            'allowed_types': [
                'application/json', 'text/csv', 'text/plain',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ],
            'allowed_extensions': ['.json', '.csv', '.txt', '.xlsx'],
            'max_size': 15 * 1024 * 1024,  # 15MB
            'max_count_per_project': 20,
            'description': 'Файл глоссария'
        }
    }
    
    # Глобальные ограничения
    GLOBAL_LIMITS = {
        'max_total_size_per_user': 100 * 1024 * 1024,  # 100MB на пользователя
        'max_total_size_per_team': 1024 * 1024 * 1024,  # 1GB на команду
        'max_total_size_per_project': 500 * 1024 * 1024,  # 500MB на проект
        'max_files_per_upload': 10,  # Максимум файлов за одну загрузку
    }
    
    @staticmethod
    def validate_file_type(file: UploadedFile, file_type: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Комплексная валидация файла по типу.
        
        Args:
            file: Загружаемый файл
            file_type: Тип файла ('avatar', 'project_image', 'project_document', 'glossary_file')
            user_id: ID пользователя для логирования
            
        Returns:
            Dict[str, Any]: Результат валидации с деталями
            
        Raises:
            FileValidationError: При ошибках валидации
        """
        if file_type not in FileValidationSystem.FILE_TYPE_CONFIGS:
            raise FileValidationError(
                f"Unknown file type: {file_type}",
                filename=getattr(file, 'name', 'unknown'),
                validation_type="file_type_config"
            )
        
        config = FileValidationSystem.FILE_TYPE_CONFIGS[file_type]
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'file_info': {
                'name': getattr(file, 'name', 'unknown'),
                'size': getattr(file, 'size', 0),
                'content_type': getattr(file, 'content_type', 'unknown'),
                'type': file_type
            }
        }
        
        try:
            # 1. Проверка наличия файла
            if not file or not hasattr(file, 'size') or not hasattr(file, 'content_type'):
                validation_result['valid'] = False
                validation_result['errors'].append("Файл не найден или поврежден")
                return validation_result
            
            # 2. Проверка размера файла
            if file.size <= 0:
                validation_result['valid'] = False
                validation_result['errors'].append("Файл пустой")
                return validation_result
            
            if file.size > config['max_size']:
                validation_result['valid'] = False
                validation_result['errors'].append(
                    f"Размер файла ({file.size} байт) превышает максимально допустимый "
                    f"({config['max_size']} байт) для {config['description']}"
                )
            
            # 3. Проверка MIME типа
            if file.content_type not in config['allowed_types']:
                validation_result['valid'] = False
                validation_result['errors'].append(
                    f"Тип файла '{file.content_type}' не разрешен для {config['description']}. "
                    f"Разрешенные типы: {', '.join(config['allowed_types'])}"
                )
            
            # 4. Проверка расширения файла
            if hasattr(file, 'name') and file.name:
                if not FilePathValidator.validate_file_extension(file.name, config['allowed_extensions']):
                    validation_result['valid'] = False
                    validation_result['errors'].append(
                        f"Расширение файла не разрешено для {config['description']}. "
                        f"Разрешенные расширения: {', '.join(config['allowed_extensions'])}"
                    )
                
                # 5. Проверка безопасности имени файла
                if not FilePathValidator.validate_filename_security(file.name):
                    validation_result['valid'] = False
                    validation_result['errors'].append(
                        f"Имя файла '{file.name}' содержит недопустимые символы или небезопасно"
                    )
            
            # 6. Дополнительные проверки безопасности
            security_check = FileValidationSystem._perform_content_security_check(file, user_id)
            if not security_check['valid']:
                validation_result['valid'] = False
                validation_result['errors'].extend(security_check['errors'])
            
            # Логируем результат валидации
            if not validation_result['valid']:
                FileOperationLogger.log_error(
                    "file_validation_failed",
                    FileValidationError(
                        f"File validation failed: {'; '.join(validation_result['errors'])}",
                        filename=getattr(file, 'name', 'unknown'),
                        validation_type=file_type
                    ),
                    user_id=user_id
                )
            
            return validation_result
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Ошибка при валидации файла: {str(e)}")
            
            FileOperationLogger.log_error(
                "file_validation_error",
                FileValidationError(
                    f"Unexpected error during file validation: {e}",
                    filename=getattr(file, 'name', 'unknown'),
                    validation_type=file_type,
                    original_error=e
                ),
                user_id=user_id
            )
            
            return validation_result
    
    @staticmethod
    def _perform_content_security_check(file: UploadedFile, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Выполнить проверки безопасности содержимого файла.
        
        Args:
            file: Загружаемый файл
            user_id: ID пользователя для логирования
            
        Returns:
            Dict[str, Any]: Результат проверки безопасности
        """
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        try:
            if not hasattr(file, 'read') or not hasattr(file, 'seek'):
                return result
            
            # Сохраняем текущую позицию
            current_pos = file.tell() if hasattr(file, 'tell') else 0
            
            try:
                # Читаем первые 2048 байт для анализа
                file.seek(0)
                content_sample = file.read(2048)
                
                # 1. Проверка на исполняемые файлы
                executable_signatures = [
                    b'MZ',  # Windows PE
                    b'\x7fELF',  # Linux ELF
                    b'\xca\xfe\xba\xbe',  # Java class
                    b'PK\x03\x04',  # ZIP (может содержать исполняемые файлы)
                ]
                
                for signature in executable_signatures:
                    if content_sample.startswith(signature):
                        result['valid'] = False
                        result['errors'].append("Обнаружен потенциально исполняемый файл")
                        
                        # Логируем нарушение безопасности
                        FileOperationLogger.log_security_violation(
                            "executable_file_upload",
                            getattr(file, 'name', 'unknown'),
                            user_id=user_id,
                            details=f"Executable signature detected: {signature.hex()}"
                        )
                        break
                
                # 2. Проверка на подозрительные скрипты
                script_patterns = [
                    b'<script',
                    b'javascript:',
                    b'vbscript:',
                    b'<?php',
                    b'<%',
                    b'#!/bin/',
                    b'#!/usr/bin/',
                ]
                
                content_lower = content_sample.lower()
                for pattern in script_patterns:
                    if pattern in content_lower:
                        result['warnings'].append(f"Обнаружен потенциально опасный контент: {pattern.decode('utf-8', errors='ignore')}")
                        
                        # Логируем предупреждение
                        FileOperationLogger.log_security_violation(
                            "suspicious_content_detected",
                            getattr(file, 'name', 'unknown'),
                            user_id=user_id,
                            details=f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}"
                        )
                
                # 3. Проверка на слишком большое количество нулевых байтов (может указывать на бинарный файл)
                null_count = content_sample.count(b'\x00')
                if null_count > len(content_sample) * 0.3:  # Более 30% нулевых байтов
                    result['warnings'].append("Файл содержит большое количество бинарных данных")
                
            finally:
                # Возвращаем файл в исходную позицию
                if hasattr(file, 'seek'):
                    file.seek(current_pos)
                    
        except Exception as e:
            # Логируем ошибку, но не блокируем загрузку
            FileOperationLogger.log_error("content_security_check", e, user_id=user_id)
            result['warnings'].append("Не удалось выполнить полную проверку безопасности файла")
        
        return result
    
    @staticmethod
    def check_file_count_limits(file_type: str, current_count: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Проверить ограничения на количество файлов.
        
        Args:
            file_type: Тип файла
            current_count: Текущее количество файлов данного типа
            user_id: ID пользователя для логирования
            
        Returns:
            Dict[str, Any]: Результат проверки ограничений
        """
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        if file_type not in FileValidationSystem.FILE_TYPE_CONFIGS:
            result['valid'] = False
            result['errors'].append(f"Неизвестный тип файла: {file_type}")
            return result
        
        config = FileValidationSystem.FILE_TYPE_CONFIGS[file_type]
        
        # Проверяем ограничения по количеству
        if file_type == 'avatar' and 'max_count_per_user' in config:
            if current_count >= config['max_count_per_user']:
                result['valid'] = False
                result['errors'].append(
                    f"Превышено максимальное количество файлов типа {config['description']} "
                    f"({config['max_count_per_user']})"
                )
        elif 'max_count_per_project' in config:
            if current_count >= config['max_count_per_project']:
                result['valid'] = False
                result['errors'].append(
                    f"Превышено максимальное количество файлов типа {config['description']} "
                    f"для проекта ({config['max_count_per_project']})"
                )
            elif current_count >= config['max_count_per_project'] * 0.8:  # 80% от лимита
                result['warnings'].append(
                    f"Приближение к лимиту файлов типа {config['description']}: "
                    f"{current_count}/{config['max_count_per_project']}"
                )
        
        return result
    
    @staticmethod
    def check_storage_limits(user_id: int, team_id: Optional[int] = None, 
                           project_id: Optional[int] = None, additional_size: int = 0) -> Dict[str, Any]:
        """
        Проверить ограничения на использование дискового пространства.
        
        Args:
            user_id: ID пользователя
            team_id: ID команды (опционально)
            project_id: ID проекта (опционально)
            additional_size: Размер добавляемого файла
            
        Returns:
            Dict[str, Any]: Результат проверки ограничений
        """
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        try:
            # Получаем текущее использование дискового пространства
            current_usage = FileValidationSystem._calculate_current_usage(user_id, team_id, project_id)
            
            # Проверяем ограничения пользователя
            user_total = current_usage['user_total'] + additional_size
            if user_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_user']:
                result['valid'] = False
                result['errors'].append(
                    f"Превышен лимит дискового пространства для пользователя: "
                    f"{user_total} байт из {FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_user']} байт"
                )
            elif user_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_user'] * 0.8:
                result['warnings'].append(
                    f"Использовано более 80% дискового пространства пользователя: "
                    f"{user_total}/{FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_user']} байт"
                )
            
            # Проверяем ограничения команды
            if team_id:
                team_total = current_usage['team_total'] + additional_size
                if team_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_team']:
                    result['valid'] = False
                    result['errors'].append(
                        f"Превышен лимит дискового пространства для команды: "
                        f"{team_total} байт из {FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_team']} байт"
                    )
                elif team_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_team'] * 0.8:
                    result['warnings'].append(
                        f"Использовано более 80% дискового пространства команды: "
                        f"{team_total}/{FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_team']} байт"
                    )
            
            # Проверяем ограничения проекта
            if project_id:
                project_total = current_usage['project_total'] + additional_size
                if project_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_project']:
                    result['valid'] = False
                    result['errors'].append(
                        f"Превышен лимит дискового пространства для проекта: "
                        f"{project_total} байт из {FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_project']} байт"
                    )
                elif project_total > FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_project'] * 0.8:
                    result['warnings'].append(
                        f"Использовано более 80% дискового пространства проекта: "
                        f"{project_total}/{FileValidationSystem.GLOBAL_LIMITS['max_total_size_per_project']} байт"
                    )
            
        except Exception as e:
            FileOperationLogger.log_error("storage_limits_check", e, user_id=user_id)
            result['warnings'].append("Не удалось проверить ограничения дискового пространства")
        
        return result
    
    @staticmethod
    def _calculate_current_usage(user_id: int, team_id: Optional[int] = None, 
                               project_id: Optional[int] = None) -> Dict[str, int]:
        """
        Вычислить текущее использование дискового пространства.
        
        Args:
            user_id: ID пользователя
            team_id: ID команды
            project_id: ID проекта
            
        Returns:
            Dict[str, int]: Словарь с размерами использования
        """
        usage = {
            'user_total': 0,
            'team_total': 0,
            'project_total': 0
        }
        
        try:
            # Размер файлов пользователя
            user_path = FilePathManager.get_user_path(user_id)
            if user_path.exists():
                usage['user_total'] = FileValidationSystem._get_directory_size(user_path)
            
            # Размер файлов команды
            if team_id:
                team_path = FilePathManager.get_team_path(team_id)
                if team_path.exists():
                    usage['team_total'] = FileValidationSystem._get_directory_size(team_path)
            
            # Размер файлов проекта
            if project_id and team_id:
                # Нужно получить content_folder из проекта
                # Это требует импорта модели, что может создать циклическую зависимость
                # Поэтому пока оставляем заглушку
                usage['project_total'] = 0
                
        except Exception as e:
            FileOperationLogger.log_error("calculate_usage", e, user_id=user_id)
        
        return usage
    
    @staticmethod
    def _get_directory_size(path: Path) -> int:
        """
        Получить размер папки в байтах.
        
        Args:
            path: Путь к папке
            
        Returns:
            int: Размер папки в байтах
        """
        total_size = 0
        try:
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception:
            pass  # Игнорируем ошибки доступа к файлам
        
        return total_size
    
    @staticmethod
    def check_user_permissions(user, file_type: str, target_object=None) -> Dict[str, Any]:
        """
        Проверить права доступа пользователя для загрузки файла.
        
        Args:
            user: Объект пользователя
            file_type: Тип файла
            target_object: Целевой объект (проект, команда и т.д.)
            
        Returns:
            Dict[str, Any]: Результат проверки прав доступа
        """
        result = {'valid': True, 'errors': [], 'warnings': []}
        
        try:
            # Проверка для аватарки - пользователь может загружать только свою
            if file_type == 'avatar':
                # Всегда разрешено для собственной аватарки
                return result
            
            # Проверка для файлов проекта
            if file_type in ['project_image', 'project_document', 'glossary_file']:
                if not target_object:
                    result['valid'] = False
                    result['errors'].append("Не указан целевой проект для загрузки файла")
                    return result
                
                # Проверяем, является ли пользователь членом команды проекта
                if hasattr(target_object, 'team'):
                    team = target_object.team
                    
                    # Проверяем членство в команде
                    if not hasattr(team, 'members') or not team.members.filter(id=user.id).exists():
                        result['valid'] = False
                        result['errors'].append("У вас нет прав для загрузки файлов в этот проект")
                        
                        # Логируем попытку несанкционированного доступа
                        FileOperationLogger.log_security_violation(
                            "unauthorized_file_upload",
                            f"project_{target_object.id}",
                            user_id=user.id,
                            details=f"User {user.id} attempted to upload {file_type} to project {target_object.id} without team membership"
                        )
                        return result
                    
                    # Дополнительные проверки для определенных типов файлов
                    if file_type == 'glossary_file':
                        # Для глоссария могут требоваться дополнительные права
                        # Пока разрешаем всем членам команды
                        pass
                
            return result
            
        except Exception as e:
            FileOperationLogger.log_error("permission_check", e, user_id=getattr(user, 'id', None))
            result['valid'] = False
            result['errors'].append("Ошибка при проверке прав доступа")
            return result