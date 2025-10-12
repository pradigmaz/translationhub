# users/models.py

from django.db import models
from django.core.files.storage import default_storage
from PIL import Image
import os
import logging
# AbstractUser импортируется как основа для создания своей модели пользователя
# со всеми стандартными полями и методами (username, password, email и т.д.).
from django.contrib.auth.models import AbstractUser
from utils.file_system import (
    user_avatar_upload_path, 
    DirectoryManager, 
    FileCleanupManager,
    FileOperationLogger,
    FileSystemError
)

# Создается новый класс User, который наследует все от AbstractUser.
# Это стандартная практика для расширения функционала пользователя.
class User(AbstractUser):
    """
    Кастомная модель пользователя.
    """
    # models.CharField - это текстовое поле с ограниченной длиной.
    display_name = models.CharField(
        # Максимальная длина строки в базе данных.
        max_length=100,
        # blank=True означает, что это поле не обязательно для заполнения в формах.
        blank=True,
        # help_text - это текстовая подсказка, которая будет отображаться в админ-панели.
        help_text="Отображаемый никнейм"
    )
    
    # models.ImageField - поле для загрузки изображений
    avatar = models.ImageField(
        # upload_to - функция для генерации пути к файлу в персонализированной структуре
        upload_to=user_avatar_upload_path,
        # blank=True - поле не обязательно для заполнения в формах
        blank=True,
        # null=True - поле может быть пустым в базе данных
        null=True,
        help_text="Аватарка пользователя"
    )
    
    def save(self, *args, **kwargs):
        """
        Переопределяем метод save для обработки аватарки.
        Автоматически создает папку пользователя и изменяет размер аватарки до 200x200px.
        """
        # Проверяем, создается ли новый пользователь
        is_new_user = self.pk is None
        
        # Сохраняем старую аватарку для удаления
        old_avatar = None
        if not is_new_user:
            try:
                old_user = User.objects.get(pk=self.pk)
                old_avatar = old_user.avatar
            except User.DoesNotExist:
                pass
        
        # Создаем папку пользователя если загружается аватарка
        if self.avatar:
            try:
                # Для нового пользователя нужно сначала сохранить, чтобы получить ID
                if is_new_user:
                    super().save(*args, **kwargs)
                    is_new_user = False  # Теперь у нас есть ID
                
                # Создаем папку пользователя
                DirectoryManager.create_user_directory(self.id)
                FileOperationLogger.log_directory_created(f"users/{self.id}", self.id)
                
            except FileSystemError as e:
                # Логируем ошибку, но не прерываем сохранение пользователя
                FileOperationLogger.log_error("create_user_directory", e)
                logging.warning(f"Failed to create directory for user {self.id}: {e}")
        
        # Сохраняем пользователя если еще не сохранили
        if is_new_user:
            super().save(*args, **kwargs)
        
        # Обрабатываем новую аватарку
        if self.avatar:
            try:
                self._resize_avatar()
                FileOperationLogger.log_file_uploaded(str(self.avatar), self.id, self.avatar.size)
            except FileSystemError as e:
                # Ошибки файловой системы логируем как предупреждения
                FileOperationLogger.log_error("resize_avatar", e)
                logging.warning(f"Failed to resize avatar for user {self.id}: {e}")
            except Exception as e:
                # Неожиданные ошибки логируем как ошибки
                FileOperationLogger.log_error("resize_avatar", e)
                logging.error(f"Unexpected error resizing avatar for user {self.id}: {e}")
        
        # Удаляем старую аватарку если она была заменена
        if old_avatar and old_avatar != self.avatar and old_avatar.name:
            try:
                if default_storage.exists(old_avatar.name):
                    default_storage.delete(old_avatar.name)
                    FileOperationLogger.log_file_deleted(old_avatar.name, self.id)
            except Exception as e:
                FileOperationLogger.log_error("delete_old_avatar", e)
                logging.warning(f"Failed to delete old avatar for user {self.id}: {e}")
    
    def _resize_avatar(self):
        """
        Изменяет размер аватарки до 200x200px с сохранением пропорций.
        Включает улучшенную обработку ошибок и логирование.
        """
        if not self.avatar:
            return
        
        try:
            # Проверяем, что файл существует (в тестах файл может не существовать на диске)
            if not os.path.exists(self.avatar.path):
                # В тестовой среде файл может не существовать на диске - это нормально
                logging.info(f"Avatar file does not exist on disk (possibly in test environment): {self.avatar.path}")
                return
            
            # Открываем изображение
            img = Image.open(self.avatar.path)
            
            # Конвертируем в RGB если необходимо (для PNG с прозрачностью)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Создаем белый фон
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Изменяем размер с сохранением пропорций
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            # Создаем квадратное изображение 200x200 с центрированием
            square_img = Image.new('RGB', (200, 200), (255, 255, 255))
            
            # Вычисляем позицию для центрирования
            x = (200 - img.width) // 2
            y = (200 - img.height) // 2
            
            square_img.paste(img, (x, y))
            
            # Сохраняем обработанное изображение
            square_img.save(self.avatar.path, 'JPEG', quality=85, optimize=True)
            
            FileOperationLogger.log_file_uploaded(f"Resized avatar: {self.avatar.path}", self.id, os.path.getsize(self.avatar.path))
            
        except FileSystemError:
            # Перебрасываем FileSystemError без изменений
            raise
        except Exception as e:
            # Логируем ошибку и перебрасываем как FileSystemError
            error_msg = f"Failed to resize avatar for user {self.id}: {e}"
            FileOperationLogger.log_error("resize_avatar", e)
            raise FileSystemError(error_msg) from e
    
    def delete(self, *args, **kwargs):
        """
        Переопределяем метод delete для удаления всех файлов пользователя при удалении.
        Использует новую систему управления файлами для полной очистки папки пользователя.
        """
        user_id = self.id
        
        try:
            # Используем FileCleanupManager для полной очистки файлов пользователя
            FileCleanupManager.cleanup_user_files(user_id)
            FileOperationLogger.log_file_deleted(f"All files for user {user_id}", user_id)
            
        except FileSystemError as e:
            # Логируем ошибку, но не прерываем удаление пользователя из БД
            FileOperationLogger.log_error("cleanup_user_files_on_delete", e)
            logging.warning(f"Failed to cleanup files for user {user_id}: {e}")
            
            # Fallback: пытаемся удалить хотя бы аватарку старым способом
            try:
                if self.avatar and self.avatar.name:
                    if default_storage.exists(self.avatar.name):
                        default_storage.delete(self.avatar.name)
                        FileOperationLogger.log_file_deleted(self.avatar.name, user_id)
            except Exception as fallback_error:
                FileOperationLogger.log_error("fallback_avatar_delete", fallback_error)
                logging.warning(f"Failed to delete avatar for user {user_id}: {fallback_error}")
        
        except Exception as e:
            # Неожиданная ошибка - логируем и продолжаем
            FileOperationLogger.log_error("unexpected_error_on_user_delete", e)
            logging.error(f"Unexpected error during user {user_id} file cleanup: {e}")
        
        # Удаляем пользователя из базы данных
        super().delete(*args, **kwargs)