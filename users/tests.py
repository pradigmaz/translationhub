from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from PIL import Image
import io
import os
from .models import User
from .forms import ProfileForm


class AvatarHandlingTestCase(TestCase):
    """Тесты для обработки аватарок пользователей"""
    
    def setUp(self):
        """Создаем тестового пользователя"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def create_test_image(self, format='JPEG', size=(100, 100)):
        """Создает тестовое изображение в памяти"""
        image = Image.new('RGB', size, color='red')
        image_io = io.BytesIO()
        image.save(image_io, format=format)
        image_io.seek(0)
        return image_io
    
    def test_avatar_upload_valid_jpeg(self):
        """Тест загрузки валидного JPEG файла"""
        image_data = self.create_test_image('JPEG')
        uploaded_file = SimpleUploadedFile(
            'test_avatar.jpg',
            image_data.getvalue(),
            content_type='image/jpeg'
        )
        
        form_data = {
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = ProfileForm(data=form_data, files={'avatar': uploaded_file}, instance=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_avatar_upload_valid_png(self):
        """Тест загрузки валидного PNG файла"""
        image_data = self.create_test_image('PNG')
        uploaded_file = SimpleUploadedFile(
            'test_avatar.png',
            image_data.getvalue(),
            content_type='image/png'
        )
        
        form_data = {
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = ProfileForm(data=form_data, files={'avatar': uploaded_file}, instance=self.user)
        
        self.assertTrue(form.is_valid())
    
    def test_avatar_upload_invalid_format(self):
        """Тест загрузки файла неподдерживаемого формата"""
        uploaded_file = SimpleUploadedFile(
            'test_avatar.gif',
            b'fake gif content',
            content_type='image/gif'
        )
        
        form_data = {
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = ProfileForm(data=form_data, files={'avatar': uploaded_file}, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('avatar', form.errors)
    
    def test_avatar_upload_too_large(self):
        """Тест загрузки слишком большого файла"""
        # Создаем большое изображение (больше 2MB)
        large_image_data = self.create_test_image('JPEG', size=(2000, 2000))
        
        # Создаем файл размером больше 2MB
        large_content = large_image_data.getvalue() * 100  # Увеличиваем размер
        
        uploaded_file = SimpleUploadedFile(
            'large_avatar.jpg',
            large_content,
            content_type='image/jpeg'
        )
        
        form_data = {
            'display_name': 'Test User',
            'email': 'test@example.com'
        }
        form = ProfileForm(data=form_data, files={'avatar': uploaded_file}, instance=self.user)
        
        self.assertFalse(form.is_valid())
        self.assertIn('avatar', form.errors)
    
    def test_avatar_template_tag(self):
        """Тест template tag для аватарки"""
        from core.templatetags.form_tags import avatar_url
        
        # Тест без аватарки
        self.assertIsNone(avatar_url(self.user))
        
        # Тест с аватаркой
        image_data = self.create_test_image('JPEG')
        uploaded_file = SimpleUploadedFile(
            'test_avatar.jpg',
            image_data.getvalue(),
            content_type='image/jpeg'
        )
        
        self.user.avatar = uploaded_file
        self.user.save()
        
        # Проверяем, что URL аватарки возвращается
        avatar_url_result = avatar_url(self.user)
        self.assertIsNotNone(avatar_url_result)
        self.assertTrue(avatar_url_result.startswith('/media/avatars/'))
    
    def tearDown(self):
        """Очистка после тестов"""
        # Удаляем загруженные тестовые файлы
        if self.user.avatar and self.user.avatar.name:
            if default_storage.exists(self.user.avatar.name):
                default_storage.delete(self.user.avatar.name)
