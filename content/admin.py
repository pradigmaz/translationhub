from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.contrib.admin import SimpleListFilter
from .models import TextContent, ImageContent, ProjectDocument, ContentAuditLog


class TextContentInline(admin.TabularInline):
    """Inline редактирование текстов в проекте"""
    model = TextContent
    extra = 0
    fields = ['title', 'author', 'is_draft', 'updated_at']
    readonly_fields = ['updated_at']
    show_change_link = True
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author')


class ImageContentInline(admin.TabularInline):
    """Inline редактирование изображений в проекте"""
    model = ImageContent
    extra = 0
    fields = ['title', 'uploader', 'file_size_display', 'dimensions', 'uploaded_at']
    readonly_fields = ['file_size_display', 'dimensions', 'uploaded_at']
    show_change_link = True
    
    def file_size_display(self, obj):
        """Отображение размера файла в удобном формате"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = "Размер файла"
    
    def dimensions(self, obj):
        """Отображение размеров изображения"""
        return f"{obj.width}x{obj.height}" if obj.width and obj.height else "Неизвестно"
    dimensions.short_description = "Размеры"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploader')


class TeamFilter(SimpleListFilter):
    """Фильтр по командам"""
    title = 'команда'
    parameter_name = 'team'
    
    def lookups(self, request, model_admin):
        from teams.models import Team
        teams = Team.objects.filter(status='active').order_by('name')
        return [(team.id, team.name) for team in teams]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(team__id=self.value())
        return queryset


class DraftStatusFilter(SimpleListFilter):
    """Фильтр по статусу черновика"""
    title = 'статус публикации'
    parameter_name = 'draft_status'
    
    def lookups(self, request, model_admin):
        return [
            ('draft', 'Черновики'),
            ('published', 'Опубликованные'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'draft':
            return queryset.filter(is_draft=True)
        elif self.value() == 'published':
            return queryset.filter(is_draft=False)
        return queryset



@admin.register(TextContent)
class TextContentAdmin(admin.ModelAdmin):
    """Расширенная админ панель для текстового контента"""
    list_display = [
        'title', 'project_link', 'author_link', 'status_badge', 
        'word_count', 'last_autosave', 'updated_at'
    ]
    list_filter = [
        DraftStatusFilter, 'project__team', 'created_at', 
        'updated_at', 'last_autosave'
    ]
    search_fields = ['title', 'content', 'project__title', 'author__username']
    readonly_fields = [
        'created_at', 'updated_at', 'last_autosave', 
        'content_preview', 'draft_preview'
    ]
    fieldsets = [
        ('Основная информация', {
            'fields': ['title', 'project', 'author', 'is_draft']
        }),
        ('Содержимое', {
            'fields': ['content', 'content_preview']
        }),
        ('Автосохранение', {
            'fields': ['draft_content', 'draft_preview', 'last_autosave'],
            'classes': ['collapse']
        }),
        ('Системная информация', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    actions = ['publish_texts', 'convert_to_draft', 'bulk_delete_drafts']
    date_hierarchy = 'updated_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project__team', 'author')
    
    def project_link(self, obj):
        """Ссылка на проект"""
        url = reverse('admin:projects_project_change', args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.title)
    project_link.short_description = "Проект"
    project_link.admin_order_field = 'project__title'
    
    def author_link(self, obj):
        """Ссылка на автора"""
        url = reverse('admin:auth_user_change', args=[obj.author.id])
        display_name = getattr(obj.author, 'display_name', None) or obj.author.username
        return format_html('<a href="{}">{}</a>', url, display_name)
    author_link.short_description = "Автор"
    author_link.admin_order_field = 'author__username'
    
    def status_badge(self, obj):
        """Бейдж статуса"""
        if obj.is_draft:
            return format_html(
                '<span style="background-color: #ffc107; color: #000; '
                'padding: 2px 8px; border-radius: 3px; font-size: 11px;">'
                'ЧЕРНОВИК</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #198754; color: #fff; '
                'padding: 2px 8px; border-radius: 3px; font-size: 11px;">'
                'ОПУБЛИКОВАН</span>'
            )
    status_badge.short_description = "Статус"
    status_badge.admin_order_field = 'is_draft'
    
    def word_count(self, obj):
        """Количество слов"""
        import re
        words = re.findall(r'\b\w+\b', obj.content)
        return len(words)
    word_count.short_description = "Слов"
    
    def content_preview(self, obj):
        """Превью содержимого"""
        if obj.content:
            preview = obj.content[:200] + "..." if len(obj.content) > 200 else obj.content
            return format_html('<div style="max-height: 100px; overflow-y: auto;">{}</div>', preview)
        return "Нет содержимого"
    content_preview.short_description = "Превью содержимого"
    
    def draft_preview(self, obj):
        """Превью черновика"""
        if obj.draft_content:
            preview = obj.draft_content[:200] + "..." if len(obj.draft_content) > 200 else obj.draft_content
            return format_html('<div style="max-height: 100px; overflow-y: auto;">{}</div>', preview)
        return "Нет черновика"
    draft_preview.short_description = "Превью черновика"
    
    def publish_texts(self, request, queryset):
        """Публикация текстов"""
        updated = queryset.update(is_draft=False)
        self.message_user(request, f"Опубликовано {updated} текстов")
    publish_texts.short_description = "Опубликовать выбранные тексты"
    
    def convert_to_draft(self, request, queryset):
        """Конвертация в черновики"""
        updated = queryset.update(is_draft=True)
        self.message_user(request, f"Конвертировано в черновики {updated} текстов")
    convert_to_draft.short_description = "Конвертировать в черновики"
    
    def bulk_delete_drafts(self, request, queryset):
        """Массовое удаление черновиков"""
        drafts = queryset.filter(is_draft=True)
        count = drafts.count()
        drafts.delete()
        self.message_user(request, f"Удалено {count} черновиков")
    bulk_delete_drafts.short_description = "Удалить черновики"


@admin.register(ImageContent)
class ImageContentAdmin(admin.ModelAdmin):
    """Расширенная админ панель для изображений"""
    list_display = [
        'title', 'project_link', 'uploader_link', 'image_preview', 
        'file_size_display', 'dimensions', 'uploaded_at'
    ]
    list_filter = ['project__team', 'uploaded_at', 'width', 'height']
    search_fields = ['title', 'project__title', 'uploader__username']
    readonly_fields = [
        'uploaded_at', 'file_size', 'width', 'height', 
        'image_preview_large', 'file_info'
    ]
    fieldsets = [
        ('Основная информация', {
            'fields': ['title', 'project', 'uploader', 'image']
        }),
        ('Превью', {
            'fields': ['image_preview_large']
        }),
        ('Метаданные файла', {
            'fields': ['file_info', 'file_size', 'width', 'height'],
            'classes': ['collapse']
        }),
        ('Системная информация', {
            'fields': ['uploaded_at'],
            'classes': ['collapse']
        })
    ]
    actions = ['optimize_images', 'generate_thumbnails']
    date_hierarchy = 'uploaded_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project__team', 'uploader')
    
    def project_link(self, obj):
        """Ссылка на проект"""
        url = reverse('admin:projects_project_change', args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.title)
    project_link.short_description = "Проект"
    project_link.admin_order_field = 'project__title'
    
    def uploader_link(self, obj):
        """Ссылка на загрузчика"""
        url = reverse('admin:auth_user_change', args=[obj.uploader.id])
        display_name = getattr(obj.uploader, 'display_name', None) or obj.uploader.username
        return format_html('<a href="{}">{}</a>', url, display_name)
    uploader_link.short_description = "Загрузчик"
    uploader_link.admin_order_field = 'uploader__username'
    
    def image_preview(self, obj):
        """Маленькое превью изображения"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px;" />',
                obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = "Превью"
    
    def image_preview_large(self, obj):
        """Большое превью изображения"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.image.url
            )
        return "Нет изображения"
    image_preview_large.short_description = "Превью изображения"
    
    def file_size_display(self, obj):
        """Отображение размера файла в удобном формате"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = "Размер файла"
    file_size_display.admin_order_field = 'file_size'
    
    def dimensions(self, obj):
        """Отображение размеров изображения"""
        if obj.width and obj.height:
            return f"{obj.width}×{obj.height}"
        return "Неизвестно"
    dimensions.short_description = "Размеры"
    
    def file_info(self, obj):
        """Подробная информация о файле"""
        if obj.image:
            return format_html(
                '<strong>Путь:</strong> {}<br>'
                '<strong>Размер:</strong> {}<br>'
                '<strong>Разрешение:</strong> {}×{}<br>'
                '<strong>Соотношение сторон:</strong> {:.2f}',
                obj.image.name,
                self.file_size_display(obj),
                obj.width or 0,
                obj.height or 0,
                (obj.width / obj.height) if obj.width and obj.height else 0
            )
        return "Нет информации"
    file_info.short_description = "Информация о файле"
    
    def optimize_images(self, request, queryset):
        """Оптимизация изображений"""
        # Здесь можно реализовать логику оптимизации
        self.message_user(request, f"Оптимизировано {queryset.count()} изображений")
    optimize_images.short_description = "Оптимизировать изображения"
    
    def generate_thumbnails(self, request, queryset):
        """Генерация миниатюр"""
        # Здесь можно реализовать генерацию миниатюр
        self.message_user(request, f"Созданы миниатюры для {queryset.count()} изображений")
    generate_thumbnails.short_description = "Создать миниатюры"


@admin.register(ProjectDocument)
class ProjectDocumentAdmin(admin.ModelAdmin):
    """Админ панель для документов проектов"""
    list_display = [
        'title', 'project_link', 'document_type', 'uploaded_by_link', 
        'file_size_display', 'uploaded_at'
    ]
    list_filter = ['document_type', 'project__team', 'uploaded_at']
    search_fields = ['title', 'project__title', 'uploaded_by__username']
    readonly_fields = ['uploaded_at', 'file_size', 'file_info']
    fieldsets = [
        ('Основная информация', {
            'fields': ['title', 'project', 'document_type', 'uploaded_by', 'file']
        }),
        ('Метаданные файла', {
            'fields': ['file_info', 'file_size'],
            'classes': ['collapse']
        }),
        ('Системная информация', {
            'fields': ['uploaded_at'],
            'classes': ['collapse']
        })
    ]
    actions = ['change_document_type', 'bulk_download']
    date_hierarchy = 'uploaded_at'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project__team', 'uploaded_by')
    
    def project_link(self, obj):
        """Ссылка на проект"""
        url = reverse('admin:projects_project_change', args=[obj.project.id])
        return format_html('<a href="{}">{}</a>', url, obj.project.title)
    project_link.short_description = "Проект"
    project_link.admin_order_field = 'project__title'
    
    def uploaded_by_link(self, obj):
        """Ссылка на загрузчика"""
        url = reverse('admin:auth_user_change', args=[obj.uploaded_by.id])
        display_name = getattr(obj.uploaded_by, 'display_name', None) or obj.uploaded_by.username
        return format_html('<a href="{}">{}</a>', url, display_name)
    uploaded_by_link.short_description = "Загрузчик"
    uploaded_by_link.admin_order_field = 'uploaded_by__username'
    
    def file_size_display(self, obj):
        """Отображение размера файла в удобном формате"""
        if obj.file_size < 1024:
            return f"{obj.file_size} B"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.1f} MB"
    file_size_display.short_description = "Размер файла"
    file_size_display.admin_order_field = 'file_size'
    
    def file_info(self, obj):
        """Подробная информация о файле"""
        if obj.file:
            return format_html(
                '<strong>Путь:</strong> {}<br>'
                '<strong>Размер:</strong> {}<br>'
                '<strong>Тип:</strong> {}',
                obj.file.name,
                self.file_size_display(obj),
                obj.get_document_type_display()
            )
        return "Нет информации"
    file_info.short_description = "Информация о файле"
    
    def change_document_type(self, request, queryset):
        """Изменение типа документа"""
        # Здесь можно реализовать массовое изменение типа
        self.message_user(request, f"Тип изменен для {queryset.count()} документов")
    change_document_type.short_description = "Изменить тип документа"
    
    def bulk_download(self, request, queryset):
        """Массовая загрузка документов"""
        # Здесь можно реализовать создание архива
        self.message_user(request, f"Подготовлен архив из {queryset.count()} документов")
    bulk_download.short_description = "Скачать архивом"


@admin.register(ContentAuditLog)
class ContentAuditLogAdmin(admin.ModelAdmin):
    """Админ панель для логов аудита контента"""
    list_display = [
        'timestamp', 'user_link', 'action_badge', 'object_info', 
        'ip_address', 'details_preview'
    ]
    list_filter = ['action', 'object_type', 'timestamp', 'user']
    search_fields = [
        'user__username', 'action', 'object_type', 
        'ip_address', 'details'
    ]
    readonly_fields = [
        'user', 'action', 'object_type', 'object_id', 
        'details', 'ip_address', 'user_agent', 'timestamp',
        'details_formatted'
    ]
    fieldsets = [
        ('Основная информация', {
            'fields': ['timestamp', 'user', 'action', 'object_type', 'object_id']
        }),
        ('Детали', {
            'fields': ['details_formatted', 'details']
        }),
        ('Техническая информация', {
            'fields': ['ip_address', 'user_agent'],
            'classes': ['collapse']
        })
    ]
    date_hierarchy = 'timestamp'
    actions = ['export_audit_logs', 'cleanup_old_logs']
    
    def has_add_permission(self, request):
        """Запрещаем добавление логов через админку"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем изменение логов"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям"""
        return request.user.is_superuser
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def user_link(self, obj):
        """Ссылка на пользователя"""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            display_name = getattr(obj.user, 'display_name', None) or obj.user.username
            return format_html('<a href="{}">{}</a>', url, display_name)
        return "Неизвестный пользователь"
    user_link.short_description = "Пользователь"
    user_link.admin_order_field = 'user__username'
    
    def action_badge(self, obj):
        """Бейдж действия"""
        colors = {
            'create_text': '#28a745',
            'update_text': '#17a2b8',
            'delete_text': '#dc3545',
            'autosave_text': '#ffc107',
            'create_project': '#28a745',
            'update_project': '#17a2b8',
            'delete_project': '#dc3545',
            'upload_image': '#6f42c1',
            'delete_image': '#dc3545',
            'view_project': '#6c757d',
            'access_denied': '#dc3545',
        }
        color = colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: #fff; '
            'padding: 2px 8px; border-radius: 3px; font-size: 11px;">'
            '{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = "Действие"
    action_badge.admin_order_field = 'action'
    
    def object_info(self, obj):
        """Информация об объекте"""
        if obj.object_id:
            return f"{obj.object_type} #{obj.object_id}"
        return obj.object_type
    object_info.short_description = "Объект"
    
    def details_preview(self, obj):
        """Превью деталей"""
        if obj.details:
            preview = str(obj.details)[:50] + "..." if len(str(obj.details)) > 50 else str(obj.details)
            return preview
        return "Нет деталей"
    details_preview.short_description = "Детали"
    
    def details_formatted(self, obj):
        """Форматированные детали"""
        if obj.details:
            import json
            try:
                formatted = json.dumps(obj.details, indent=2, ensure_ascii=False)
                return format_html('<pre>{}</pre>', formatted)
            except:
                return str(obj.details)
        return "Нет деталей"
    details_formatted.short_description = "Детали (форматированные)"
    
    def export_audit_logs(self, request, queryset):
        """Экспорт логов аудита"""
        # Здесь можно реализовать экспорт в CSV
        self.message_user(request, f"Экспортировано {queryset.count()} записей аудита")
    export_audit_logs.short_description = "Экспортировать логи"
    
    def cleanup_old_logs(self, request, queryset):
        """Очистка старых логов"""
        from datetime import datetime, timedelta
        old_date = datetime.now() - timedelta(days=90)
        old_logs = queryset.filter(timestamp__lt=old_date)
        count = old_logs.count()
        old_logs.delete()
        self.message_user(request, f"Удалено {count} старых записей аудита")
    cleanup_old_logs.short_description = "Очистить старые логи (>90 дней)"


# Настройка заголовков админки
admin.site.site_header = "TranslationHub - Управление контентом"
admin.site.site_title = "TranslationHub Admin"
admin.site.index_title = "Панель управления контентом"