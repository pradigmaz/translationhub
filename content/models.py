from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from projects.models import Project
from utils.file_system import project_image_upload_path, project_document_upload_path


class TextContentManager(models.Manager):
    """Менеджер для модели TextContent с оптимизированными запросами"""
    
    def for_user(self, user):
        """Возвращает тексты, доступные пользователю через его команды"""
        return self.select_related('project__team', 'author').filter(
            project__team__members=user,
            project__team__teammembership__is_active=True,
            project__team__status='active'
        ).distinct()
    
    def with_related(self):
        """Возвращает тексты с предзагруженными связанными объектами"""
        return self.select_related('project__team', 'author')
    
    def recent_for_user(self, user, limit=5):
        """Возвращает последние тексты пользователя"""
        return self.for_user(user).filter(author=user)[:limit]


class TextContent(models.Model):
    """Текстовый контент для переводчиков и редакторов"""
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        verbose_name="Проект"
    )
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    content = models.TextField(verbose_name="Содержимое")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name="Автор"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлен")
    is_draft = models.BooleanField(default=True, verbose_name="Черновик")
    
    # Для автосохранения
    draft_content = models.TextField(blank=True, verbose_name="Черновик контента")
    last_autosave = models.DateTimeField(null=True, blank=True, verbose_name="Последнее автосохранение")
    
    objects = TextContentManager()
    
    class Meta:
        verbose_name = "Текстовый контент"
        verbose_name_plural = "Текстовый контент"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['project', '-updated_at']),
            models.Index(fields=['author', '-updated_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.project.name}"
    
    def user_can_edit(self, user):
        """Проверяет, может ли пользователь редактировать текст"""
        return (
            self.project.user_has_access(user) and 
            (self.author == user or self.project.can_be_edited_by(user))
        )
    
    def user_can_view(self, user):
        """Проверяет, может ли пользователь просматривать текст"""
        return self.project.user_has_access(user)


class ImageContentManager(models.Manager):
    """Менеджер для модели ImageContent с оптимизированными запросами"""
    
    def for_user(self, user):
        """Возвращает изображения, доступные пользователю через его команды"""
        return self.select_related('project__team', 'uploader').filter(
            project__team__members=user,
            project__team__teammembership__is_active=True,
            project__team__status='active'
        ).distinct()
    
    def with_related(self):
        """Возвращает изображения с предзагруженными связанными объектами"""
        return self.select_related('project__team', 'uploader')
    
    def recent_for_user(self, user, limit=10):
        """Возвращает последние изображения пользователя"""
        return self.for_user(user).filter(uploader=user)[:limit]


class ImageContent(models.Model):
    """Изображения для заливщиков, тайперов, клинеров"""
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        verbose_name="Проект"
    )
    title = models.CharField(max_length=200, verbose_name="Название")
    image = models.ImageField(
        upload_to=project_image_upload_path, 
        verbose_name="Изображение"
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name="Загрузил"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Загружено")
    
    # Метаданные файла
    file_size = models.IntegerField(verbose_name="Размер файла (байт)")
    width = models.IntegerField(verbose_name="Ширина")
    height = models.IntegerField(verbose_name="Высота")
    
    objects = ImageContentManager()
    
    class Meta:
        verbose_name = "Изображение"
        verbose_name_plural = "Изображения"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['project', '-uploaded_at']),
            models.Index(fields=['uploader', '-uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.project.title}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        if self.image:
            # Проверка размера файла (максимум 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if self.image.size > max_size:
                raise ValidationError(f'Размер файла не должен превышать {max_size // (1024*1024)}MB')
            
            # Проверка типа файла
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(self.image.file, 'content_type') and self.image.file.content_type not in allowed_types:
                raise ValidationError('Разрешены только изображения форматов: JPEG, PNG, GIF, WebP')
    
    def user_can_edit(self, user):
        """Проверяет, может ли пользователь редактировать изображение"""
        # Используем методы из projects.models.Project
        return (
            user in self.project.team.members.filter(teammembership__is_active=True) and
            self.project.team.status == 'active' and
            (self.uploader == user or self.project.team.creator == user or user.is_superuser)
        )
    
    def user_can_view(self, user):
        """Проверяет, может ли пользователь просматривать изображение"""
        return (
            user in self.project.team.members.filter(teammembership__is_active=True) and
            self.project.team.status == 'active'
        )
    
    def save(self, *args, **kwargs):
        # Валидация перед сохранением
        self.full_clean()
        
        if self.image:
            # Автоматически заполняем метаданные
            self.file_size = self.image.size
            # Получаем размеры изображения
            try:
                from PIL import Image
                img = Image.open(self.image)
                self.width, self.height = img.size
            except ImportError:
                # Если Pillow не установлен, ставим значения по умолчанию
                self.width = 0
                self.height = 0
        super().save(*args, **kwargs)


class ProjectDocument(models.Model):
    """Документы проекта (глоссарий, заметки и т.д.)"""
    
    DOCUMENT_TYPES = [
        ('glossary', 'Глоссарий'),
        ('notes', 'Заметки'),
        ('reference', 'Справочные материалы'),
        ('other', 'Прочее'),
    ]
    
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE, 
        verbose_name="Проект",
        related_name='documents'
    )
    title = models.CharField(max_length=200, verbose_name="Название")
    document_type = models.CharField(
        max_length=20, 
        choices=DOCUMENT_TYPES, 
        default='other',
        verbose_name="Тип документа"
    )
    file = models.FileField(
        upload_to=project_document_upload_path, 
        verbose_name="Файл"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        verbose_name="Загрузил"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Загружено")
    
    # Метаданные файла
    file_size = models.IntegerField(verbose_name="Размер файла (байт)")
    
    class Meta:
        verbose_name = "Документ проекта"
        verbose_name_plural = "Документы проектов"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['project', '-uploaded_at']),
            models.Index(fields=['uploaded_by', '-uploaded_at']),
            models.Index(fields=['document_type', '-uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.project.title}"
    
    def clean(self):
        """Валидация модели"""
        super().clean()
        
        if self.file:
            # Проверка размера файла (максимум 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if self.file.size > max_size:
                raise ValidationError(f'Размер файла не должен превышать {max_size // (1024*1024)}MB')
            
            # Проверка типа файла
            allowed_types = [
                'application/pdf', 'text/plain', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/csv', 'application/json', 'text/markdown'
            ]
            if hasattr(self.file.file, 'content_type') and self.file.file.content_type not in allowed_types:
                raise ValidationError('Разрешены только документы форматов: PDF, TXT, DOC, DOCX, CSV, JSON, MD')
    
    def user_can_edit(self, user):
        """Проверяет, может ли пользователь редактировать документ"""
        return (
            user in self.project.team.members.filter(teammembership__is_active=True) and
            self.project.team.status == 'active' and
            (self.uploaded_by == user or self.project.team.creator == user or user.is_superuser)
        )
    
    def user_can_view(self, user):
        """Проверяет, может ли пользователь просматривать документ"""
        return (
            user in self.project.team.members.filter(teammembership__is_active=True) and
            self.project.team.status == 'active'
        )
    
    def save(self, *args, **kwargs):
        # Валидация перед сохранением
        self.full_clean()
        
        if self.file:
            # Автоматически заполняем размер файла
            self.file_size = self.file.size
        
        super().save(*args, **kwargs)


class ContentAuditLog(models.Model):
    """Модель для хранения логов аудита действий с контентом"""
    
    ACTION_CHOICES = [
        ('create_text', 'Создание текста'),
        ('update_text', 'Обновление текста'),
        ('delete_text', 'Удаление текста'),
        ('autosave_text', 'Автосохранение текста'),
        ('create_project', 'Создание проекта'),
        ('update_project', 'Обновление проекта'),
        ('delete_project', 'Удаление проекта'),
        ('upload_image', 'Загрузка изображения'),
        ('delete_image', 'Удаление изображения'),
        ('view_project', 'Просмотр проекта'),
        ('access_denied', 'Отказ в доступе'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Пользователь"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name="Действие"
    )
    object_type = models.CharField(
        max_length=50,
        verbose_name="Тип объекта"
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID объекта"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Детали действия"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP адрес"
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время действия"
    )
    
    class Meta:
        verbose_name = "Лог аудита контента"
        verbose_name_plural = "Логи аудита контента"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['object_type', 'object_id']),
        ]
    
    def __str__(self):
        username = self.user.username if self.user else 'Unknown'
        return f"{username} - {self.get_action_display()} ({self.timestamp})"
    
    @classmethod
    def log_action(cls, user, action, object_type, object_id=None, details=None, ip_address=None, user_agent=None):
        """Создает запись в логе аудита"""
        return cls.objects.create(
            user=user,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )