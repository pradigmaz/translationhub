"""
Django сигналы для автоматического управления файловой структурой.

Этот модуль содержит сигналы для автоматического создания папок при создании
объектов (пользователи, команды, проекты) и очистки файлов при их удалении.
"""

import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from teams.models import Team
from projects.models import Project
from utils.file_system import (
    DirectoryManager,
    FileCleanupManager,
    FileOperationLogger,
    FileSystemError
)

# Получаем модель пользователя
User = get_user_model()

# Настройка логирования
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_directory(sender, instance, created, **kwargs):
    """
    Сигнал создания папки пользователя при регистрации.
    
    Автоматически создает структуру папок для нового пользователя:
    - media/users/{user_id}/
    - media/users/{user_id}/documents/
    
    Args:
        sender: Модель User
        instance: Экземпляр пользователя
        created: True если пользователь только что создан
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:
        try:
            # Создаем папку пользователя
            success = DirectoryManager.create_user_directory(instance.id)
            
            if success:
                FileOperationLogger.log_directory_created(f"users/{instance.id}", instance.id)
                logger.info(f"Created directory structure for user {instance.id} ({instance.username})")
            else:
                logger.warning(f"Failed to create directory for user {instance.id} ({instance.username})")
                
        except FileSystemError as e:
            # Логируем ошибку файловой системы, но не прерываем создание пользователя
            FileOperationLogger.log_error("create_user_directory_signal", e)
            logger.warning(f"FileSystemError creating directory for user {instance.id}: {e}")
            
        except Exception as e:
            # Логируем неожиданные ошибки
            FileOperationLogger.log_error("create_user_directory_signal", e)
            logger.error(f"Unexpected error creating directory for user {instance.id}: {e}")


@receiver(post_save, sender=Team)
def create_team_directory(sender, instance, created, **kwargs):
    """
    Сигнал создания папки команды при создании команды.
    
    Автоматически создает структуру папок для новой команды:
    - media/teams/{team_id}/
    - media/teams/{team_id}/documents/
    - media/teams/{team_id}/projects/
    
    Args:
        sender: Модель Team
        instance: Экземпляр команды
        created: True если команда только что создана
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:
        try:
            # Создаем папку команды
            success = DirectoryManager.create_team_directory(instance.id)
            
            if success:
                FileOperationLogger.log_directory_created(f"teams/{instance.id}", instance.creator.id)
                logger.info(f"Created directory structure for team {instance.id} ({instance.name})")
            else:
                logger.warning(f"Failed to create directory for team {instance.id} ({instance.name})")
                
        except FileSystemError as e:
            # Логируем ошибку файловой системы, но не прерываем создание команды
            FileOperationLogger.log_error("create_team_directory_signal", e)
            logger.warning(f"FileSystemError creating directory for team {instance.id}: {e}")
            
        except Exception as e:
            # Логируем неожиданные ошибки
            FileOperationLogger.log_error("create_team_directory_signal", e)
            logger.error(f"Unexpected error creating directory for team {instance.id}: {e}")


@receiver(post_save, sender=Project)
def create_project_directory(sender, instance, created, **kwargs):
    """
    Сигнал создания папки проекта при создании проекта.
    
    Автоматически создает структуру папок для нового проекта:
    - media/teams/{team_id}/projects/{content_folder}/
    - media/teams/{team_id}/projects/{content_folder}/images/
    - media/teams/{team_id}/projects/{content_folder}/documents/
    - media/teams/{team_id}/projects/{content_folder}/glossary/
    
    Args:
        sender: Модель Project
        instance: Экземпляр проекта
        created: True если проект только что создан
        **kwargs: Дополнительные аргументы сигнала
    """
    if created:
        try:
            # Проверяем, что у проекта есть content_folder
            if not instance.content_folder:
                logger.warning(f"Project {instance.id} ({instance.title}) has no content_folder, skipping directory creation")
                return
            
            # Создаем папку проекта
            success = DirectoryManager.create_project_directory(
                instance.team.id, 
                instance.content_folder
            )
            
            if success:
                FileOperationLogger.log_directory_created(
                    f"teams/{instance.team.id}/projects/{instance.content_folder}",
                    instance.team.creator.id
                )
                logger.info(f"Created directory structure for project {instance.id} ({instance.title}) in team {instance.team.id}")
            else:
                logger.warning(f"Failed to create directory for project {instance.id} ({instance.title})")
                
        except FileSystemError as e:
            # Логируем ошибку файловой системы, но не прерываем создание проекта
            FileOperationLogger.log_error("create_project_directory_signal", e)
            logger.warning(f"FileSystemError creating directory for project {instance.id}: {e}")
            
        except Exception as e:
            # Логируем неожиданные ошибки
            FileOperationLogger.log_error("create_project_directory_signal", e)
            logger.error(f"Unexpected error creating directory for project {instance.id}: {e}")


@receiver(pre_delete, sender=User)
def cleanup_user_files(sender, instance, **kwargs):
    """
    Сигнал очистки файлов пользователя при удалении.
    
    Автоматически удаляет всю папку пользователя со всеми файлами:
    - media/users/{user_id}/ (включая все подпапки и файлы)
    
    Args:
        sender: Модель User
        instance: Экземпляр пользователя
        **kwargs: Дополнительные аргументы сигнала
    """
    try:
        # Очищаем файлы пользователя
        success = FileCleanupManager.cleanup_user_files(instance.id)
        
        if success:
            FileOperationLogger.log_file_deleted(f"users/{instance.id}", instance.id)
            logger.info(f"Cleaned up files for user {instance.id} ({instance.username})")
        else:
            logger.warning(f"Failed to cleanup files for user {instance.id} ({instance.username})")
            
    except FileSystemError as e:
        # Логируем ошибку файловой системы, но не прерываем удаление пользователя
        FileOperationLogger.log_error("cleanup_user_files_signal", e)
        logger.warning(f"FileSystemError cleaning up files for user {instance.id}: {e}")
        
    except Exception as e:
        # Логируем неожиданные ошибки
        FileOperationLogger.log_error("cleanup_user_files_signal", e)
        logger.error(f"Unexpected error cleaning up files for user {instance.id}: {e}")


@receiver(pre_delete, sender=Project)
def cleanup_project_files(sender, instance, **kwargs):
    """
    Сигнал очистки файлов проекта при удалении.
    
    Автоматически удаляет папку проекта со всеми файлами:
    - media/teams/{team_id}/projects/{content_folder}/ (включая все подпапки и файлы)
    
    Args:
        sender: Модель Project
        instance: Экземпляр проекта
        **kwargs: Дополнительные аргументы сигнала
    """
    try:
        # Проверяем, что у проекта есть content_folder
        if not instance.content_folder:
            logger.info(f"Project {instance.id} ({instance.title}) has no content_folder, skipping file cleanup")
            return
        
        # Очищаем файлы проекта
        success = FileCleanupManager.cleanup_project_files(
            instance.team.id,
            instance.content_folder
        )
        
        if success:
            FileOperationLogger.log_file_deleted(
                f"teams/{instance.team.id}/projects/{instance.content_folder}",
                instance.team.creator.id
            )
            logger.info(f"Cleaned up files for project {instance.id} ({instance.title}) in team {instance.team.id}")
        else:
            logger.warning(f"Failed to cleanup files for project {instance.id} ({instance.title})")
            
    except FileSystemError as e:
        # Логируем ошибку файловой системы, но не прерываем удаление проекта
        FileOperationLogger.log_error("cleanup_project_files_signal", e)
        logger.warning(f"FileSystemError cleaning up files for project {instance.id}: {e}")
        
    except Exception as e:
        # Логируем неожиданные ошибки
        FileOperationLogger.log_error("cleanup_project_files_signal", e)
        logger.error(f"Unexpected error cleaning up files for project {instance.id}: {e}")


@receiver(pre_delete, sender=Team)
def cleanup_team_files(sender, instance, **kwargs):
    """
    Сигнал очистки файлов команды при удалении.
    
    Автоматически удаляет всю папку команды со всеми проектами и файлами:
    - media/teams/{team_id}/ (включая все подпапки и файлы)
    
    Args:
        sender: Модель Team
        instance: Экземпляр команды
        **kwargs: Дополнительные аргументы сигнала
    """
    try:
        # Очищаем файлы команды
        success = FileCleanupManager.cleanup_team_files(instance.id)
        
        if success:
            FileOperationLogger.log_file_deleted(f"teams/{instance.id}", instance.creator.id)
            logger.info(f"Cleaned up files for team {instance.id} ({instance.name})")
        else:
            logger.warning(f"Failed to cleanup files for team {instance.id} ({instance.name})")
            
    except FileSystemError as e:
        # Логируем ошибку файловой системы, но не прерываем удаление команды
        FileOperationLogger.log_error("cleanup_team_files_signal", e)
        logger.warning(f"FileSystemError cleaning up files for team {instance.id}: {e}")
        
    except Exception as e:
        # Логируем неожиданные ошибки
        FileOperationLogger.log_error("cleanup_team_files_signal", e)
        logger.error(f"Unexpected error cleaning up files for team {instance.id}: {e}")


# Функция для инициализации базовых папок при запуске системы
def initialize_base_directories():
    """
    Создает базовые папки media/users/ и media/teams/ при запуске системы.
    
    Эта функция должна вызываться при инициализации приложения
    (например, в ready() методе AppConfig).
    """
    try:
        from pathlib import Path
        from django.conf import settings
        
        # Создаем базовые папки
        base_paths = [
            Path(settings.MEDIA_ROOT) / "users",
            Path(settings.MEDIA_ROOT) / "teams",
            Path(settings.MEDIA_ROOT) / "temp" / "uploads"
        ]
        
        for path in base_paths:
            if DirectoryManager.ensure_directory_exists(path):
                FileOperationLogger.log_directory_created(path)
                logger.info(f"Initialized base directory: {path}")
            else:
                logger.warning(f"Failed to initialize base directory: {path}")
                
    except Exception as e:
        FileOperationLogger.log_error("initialize_base_directories", e)
        logger.error(f"Error initializing base directories: {e}")