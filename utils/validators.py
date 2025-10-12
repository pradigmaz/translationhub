"""
Валидаторы для форм Django в системе управления файлами.

Этот модуль содержит валидаторы для использования в Django формах
для обеспечения пользовательского интерфейса с понятными сообщениями об ошибках.
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from typing import Optional, List, Dict, Any
import os

from .file_system import (
    FileValidationSystem, FilePathValidator, FileUploadError, 
    FileValidationError, FileSecurityError
)


class FileTypeValidator:
    """
    Валидатор типов файлов для Django форм.
    
    Проверяет MIME тип и расширение загружаемого файла.
    """
    
    def __init__(self, allowed_types: List[str], allowed_extensions: List[str] = None):
        """
        Инициализация валидатора.
        
        Args:
            allowed_types: Список разрешенных MIME типов
            allowed_extensions: Список разрешенных расширений (с точкой)
        """
        self.allowed_types = allowed_types
        self.allowed_extensions = allowed_extensions or []
    
    def __call__(self, file: UploadedFile):
        """
        Выполнить валидацию файла.
        
        Args:
            file: Загружаемый файл
            
        Raises:
            ValidationError: При ошибках валидации
        """
        if not file:
            return
        
        # Проверка MIME типа
        if hasattr(file, 'content_type') and file.content_type not in self.allowed_types:
            raise ValidationError(
                _('Тип файла "%(content_type)s" не разрешен. Разрешенные типы: %(allowed_types)s'),
                params={
                    'content_type': file.content_type,
                    'allowed_types': ', '.join(self.allowed_types)
                },
                code='invalid_file_type'
            )
        
        # Проверка расширения
        if self.allowed_extensions and hasattr(file, 'name') and file.name:
            _, ext = os.path.splitext(file.name.lower())
            if ext not in [e.lower() for e in self.allowed_extensions]:
                raise ValidationError(
                    _('Расширение файла "%(extension)s" не разрешено. Разрешенные расширения: %(allowed_extensions)s'),
                    params={
                        'extension': ext,
                        'allowed_extensions': ', '.join(self.allowed_extensions)
                    },
                    code='invalid_file_extension'
                )


class FileSizeValidator:
    """
    Валидатор размера файла для Django форм.
    """
    
    def __init__(self, max_size: int, min_size: int = 1):
        """
        Инициализация валидатора.
        
        Args:
            max_size: Максимальный размер файла в байтах
            min_size: Минимальный размер файла в байтах
        """
        self.max_size = max_size
        self.min_size = min_size
    
    def __call__(self, file: UploadedFile):
        """
        Выполнить валидацию размера файла.
        
        Args:
            file: Загружаемый файл
            
        Raises:
            ValidationError: При ошибках валидации
        """
        if not file or not hasattr(file, 'size'):
            return
        
        if file.size < self.min_size:
            raise ValidationError(
                _('Файл слишком маленький (%(file_size)s байт). Минимальный размер: %(min_size)s байт'),
                params={
                    'file_size': file.size,
                    'min_size': self.min_size
                },
                code='file_too_small'
            )
        
        if file.size > self.max_size:
            # Форматируем размеры для удобочитаемости
            file_size_mb = file.size / (1024 * 1024)
            max_size_mb = self.max_size / (1024 * 1024)
            
            raise ValidationError(
                _('Файл слишком большой (%(file_size).1f МБ). Максимальный размер: %(max_size).1f МБ'),
                params={
                    'file_size': file_size_mb,
                    'max_size': max_size_mb
                },
                code='file_too_large'
            )


class FileNameValidator:
    """
    Валидатор имени файла для Django форм.
    """
    
    def __call__(self, file: UploadedFile):
        """
        Выполнить валидацию имени файла.
        
        Args:
            file: Загружаемый файл
            
        Raises:
            ValidationError: При ошибках валидации
        """
        if not file or not hasattr(file, 'name') or not file.name:
            return
        
        # Проверка базовой валидности имени файла
        if not FilePathValidator.validate_filename(file.name):
            raise ValidationError(
                _('Имя файла "%(filename)s" содержит недопустимые символы или имеет недопустимый формат'),
                params={'filename': file.name},
                code='invalid_filename'
            )
        
        # Проверка безопасности имени файла
        if not FilePathValidator.validate_filename_security(file.name):
            raise ValidationError(
                _('Имя файла "%(filename)s" небезопасно или содержит подозрительные элементы'),
                params={'filename': file.name},
                code='unsafe_filename'
            )


class FileSecurityValidator:
    """
    Валидатор безопасности файла для Django форм.
    """
    
    def __call__(self, file: UploadedFile):
        """
        Выполнить проверки безопасности файла.
        
        Args:
            file: Загружаемый файл
            
        Raises:
            ValidationError: При обнаружении угроз безопасности
        """
        if not file:
            return
        
        try:
            # Используем проверки безопасности из FileValidationSystem
            security_check = FileValidationSystem._perform_content_security_check(file)
            
            if not security_check['valid']:
                raise ValidationError(
                    _('Файл не прошел проверки безопасности: %(errors)s'),
                    params={'errors': '; '.join(security_check['errors'])},
                    code='security_check_failed'
                )
            
            # Предупреждения не блокируют загрузку, но могут быть показаны пользователю
            if security_check['warnings']:
                # В Django формах нет стандартного способа показать предупреждения
                # Можно логировать или добавить в контекст формы
                pass
                
        except Exception as e:
            # Если проверка безопасности не удалась, блокируем загрузку
            raise ValidationError(
                _('Не удалось выполнить проверку безопасности файла'),
                code='security_check_error'
            )


class ComprehensiveFileValidator:
    """
    Комплексный валидатор файла для Django форм.
    
    Объединяет все проверки в один валидатор для удобства использования.
    """
    
    def __init__(self, file_type: str, user=None, target_object=None, current_file_count: int = 0):
        """
        Инициализация комплексного валидатора.
        
        Args:
            file_type: Тип файла ('avatar', 'project_image', 'project_document', 'glossary_file')
            user: Объект пользователя (для проверки прав доступа)
            target_object: Целевой объект (проект для файлов проекта)
            current_file_count: Текущее количество файлов данного типа
        """
        self.file_type = file_type
        self.user = user
        self.target_object = target_object
        self.current_file_count = current_file_count
    
    def __call__(self, file: UploadedFile):
        """
        Выполнить комплексную валидацию файла.
        
        Args:
            file: Загружаемый файл
            
        Raises:
            ValidationError: При ошибках валидации
        """
        if not file:
            return
        
        try:
            # Используем комплексную валидацию из FileValidationSystem
            validation_result = FileValidationSystem.validate_file_type(
                file, self.file_type, getattr(self.user, 'id', None)
            )
            
            if not validation_result['valid']:
                # Объединяем все ошибки в одно сообщение
                error_message = '; '.join(validation_result['errors'])
                raise ValidationError(
                    _('Файл не прошел валидацию: %(errors)s'),
                    params={'errors': error_message},
                    code='comprehensive_validation_failed'
                )
            
            # Проверяем права доступа если указан пользователь
            if self.user:
                permission_check = FileValidationSystem.check_user_permissions(
                    self.user, self.file_type, self.target_object
                )
                
                if not permission_check['valid']:
                    error_message = '; '.join(permission_check['errors'])
                    raise ValidationError(
                        _('Недостаточно прав для загрузки файла: %(errors)s'),
                        params={'errors': error_message},
                        code='permission_denied'
                    )
            
            # Проверяем ограничения на количество файлов
            count_check = FileValidationSystem.check_file_count_limits(
                self.file_type, self.current_file_count, getattr(self.user, 'id', None)
            )
            
            if not count_check['valid']:
                error_message = '; '.join(count_check['errors'])
                raise ValidationError(
                    _('Превышены ограничения на количество файлов: %(errors)s'),
                    params={'errors': error_message},
                    code='file_count_limit_exceeded'
                )
            
            # Проверяем ограничения дискового пространства
            if self.user:
                team_id = None
                project_id = None
                
                if self.target_object and hasattr(self.target_object, 'team'):
                    team_id = self.target_object.team.id
                    project_id = self.target_object.id
                
                storage_check = FileValidationSystem.check_storage_limits(
                    self.user.id, team_id, project_id, file.size
                )
                
                if not storage_check['valid']:
                    error_message = '; '.join(storage_check['errors'])
                    raise ValidationError(
                        _('Превышены ограничения дискового пространства: %(errors)s'),
                        params={'errors': error_message},
                        code='storage_limit_exceeded'
                    )
            
        except ValidationError:
            # Перебрасываем ValidationError как есть
            raise
        except (FileUploadError, FileValidationError, FileSecurityError) as e:
            # Преобразуем наши исключения в ValidationError
            raise ValidationError(
                _('Ошибка валидации файла: %(error)s'),
                params={'error': str(e)},
                code='file_validation_error'
            )
        except Exception as e:
            # Неожиданные ошибки
            raise ValidationError(
                _('Произошла неожиданная ошибка при валидации файла'),
                code='unexpected_validation_error'
            )


# Предустановленные валидаторы для различных типов файлов

def get_avatar_validators(user=None) -> List:
    """
    Получить валидаторы для аватарки пользователя.
    
    Args:
        user: Объект пользователя
        
    Returns:
        List: Список валидаторов
    """
    config = FileValidationSystem.FILE_TYPE_CONFIGS['avatar']
    
    return [
        FileTypeValidator(config['allowed_types'], config['allowed_extensions']),
        FileSizeValidator(config['max_size']),
        FileNameValidator(),
        FileSecurityValidator(),
    ]


def get_project_image_validators(user=None, project=None, current_count: int = 0) -> List:
    """
    Получить валидаторы для изображений проекта.
    
    Args:
        user: Объект пользователя
        project: Объект проекта
        current_count: Текущее количество изображений в проекте
        
    Returns:
        List: Список валидаторов
    """
    config = FileValidationSystem.FILE_TYPE_CONFIGS['project_image']
    
    validators = [
        FileTypeValidator(config['allowed_types'], config['allowed_extensions']),
        FileSizeValidator(config['max_size']),
        FileNameValidator(),
        FileSecurityValidator(),
    ]
    
    # Добавляем комплексный валидатор если есть контекст
    if user and project:
        validators.append(
            ComprehensiveFileValidator('project_image', user, project, current_count)
        )
    
    return validators


def get_project_document_validators(user=None, project=None, current_count: int = 0) -> List:
    """
    Получить валидаторы для документов проекта.
    
    Args:
        user: Объект пользователя
        project: Объект проекта
        current_count: Текущее количество документов в проекте
        
    Returns:
        List: Список валидаторов
    """
    config = FileValidationSystem.FILE_TYPE_CONFIGS['project_document']
    
    validators = [
        FileTypeValidator(config['allowed_types'], config['allowed_extensions']),
        FileSizeValidator(config['max_size']),
        FileNameValidator(),
        FileSecurityValidator(),
    ]
    
    # Добавляем комплексный валидатор если есть контекст
    if user and project:
        validators.append(
            ComprehensiveFileValidator('project_document', user, project, current_count)
        )
    
    return validators


def get_glossary_file_validators(user=None, project=None, current_count: int = 0) -> List:
    """
    Получить валидаторы для файлов глоссария.
    
    Args:
        user: Объект пользователя
        project: Объект проекта
        current_count: Текущее количество файлов глоссария в проекте
        
    Returns:
        List: Список валидаторов
    """
    config = FileValidationSystem.FILE_TYPE_CONFIGS['glossary_file']
    
    validators = [
        FileTypeValidator(config['allowed_types'], config['allowed_extensions']),
        FileSizeValidator(config['max_size']),
        FileNameValidator(),
        FileSecurityValidator(),
    ]
    
    # Добавляем комплексный валидатор если есть контекст
    if user and project:
        validators.append(
            ComprehensiveFileValidator('glossary_file', user, project, current_count)
        )
    
    return validators