# users/models.py

from django.db import models
from django.core.files.storage import default_storage
from PIL import Image
import os
# AbstractUser импортируется как основа для создания своей модели пользователя
# со всеми стандартными полями и методами (username, password, email и т.д.).
from django.contrib.auth.models import AbstractUser

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
        # upload_to - папка для сохранения загруженных файлов
        upload_to='avatars/',
        # blank=True - поле не обязательно для заполнения в формах
        blank=True,
        # null=True - поле может быть пустым в базе данных
        null=True,
        help_text="Аватарка пользователя"
    )
    
    def save(self, *args, **kwargs):
        """
        Переопределяем метод save для обработки аватарки.
        Автоматически изменяем размер загруженной аватарки до 200x200px.
        """
        # Сохраняем старую аватарку для удаления
        old_avatar = None
        if self.pk:
            try:
                old_user = User.objects.get(pk=self.pk)
                old_avatar = old_user.avatar
            except User.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Обрабатываем новую аватарку
        if self.avatar:
            self._resize_avatar()
        
        # Удаляем старую аватарку если она была заменена
        if old_avatar and old_avatar != self.avatar and old_avatar.name:
            if default_storage.exists(old_avatar.name):
                default_storage.delete(old_avatar.name)
    
    def _resize_avatar(self):
        """
        Изменяет размер аватарки до 200x200px с сохранением пропорций.
        """
        if not self.avatar:
            return
        
        try:
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
            
        except Exception as e:
            # Логируем ошибку, но не прерываем сохранение пользователя
            print(f"Ошибка при обработке аватарки: {e}")
    
    def delete(self, *args, **kwargs):
        """
        Переопределяем метод delete для удаления аватарки при удалении пользователя.
        """
        # Удаляем аватарку перед удалением пользователя
        if self.avatar and self.avatar.name:
            if default_storage.exists(self.avatar.name):
                default_storage.delete(self.avatar.name)
        
        super().delete(*args, **kwargs)