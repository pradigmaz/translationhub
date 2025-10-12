# projects/admin.py

"""
Административная панель для управления проектами и главами.

Обновления для системы статусов перевода:
- Визуальные индикаторы статусов с цветными badges и иконками
- Расширенные фильтры по статусам, типам проектов и возрастным рейтингам
- Оптимизированные запросы с select_related для лучшей производительности
- Tooltips с описаниями статусов для улучшения пользовательского опыта
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import Project, Chapter

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    # Показывает название, команду, статус с визуальным индикатором и дату создания в списке проектов.
    list_display = ('title', 'team', 'status_display', 'project_type', 'age_rating', 'created_at')
    # Добавляет фильтры по новым статусам, команде, типу проекта и возрастному рейтингу.
    list_filter = ('status', 'team', 'project_type', 'age_rating', 'created_at')
    # Добавляет поле поиска по названию и описанию.
    search_fields = ('title', 'description')
    # Группировка полей в админке для лучшей организации
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'team')
        }),
        ('Настройки проекта', {
            'fields': ('project_type', 'age_rating', 'status')
        }),
        ('Техническая информация', {
            'fields': ('content_folder',),
            'classes': ('collapse',)
        }),
    )
    # Поля только для чтения
    readonly_fields = ('created_at',)
    # Сортировка по умолчанию
    ordering = ('-created_at',)
    
    def status_display(self, obj):
        """Отображает статус с визуальным индикатором в админке"""
        badge_class = obj.get_status_badge_class()
        icon = obj.get_status_icon()
        status_text = obj.get_status_display()
        description = obj.get_status_description()
        
        return format_html(
            '<span class="badge {}" style="color: white; padding: 4px 8px; border-radius: 4px;" '
            'title="{}">'
            '<i class="{}" style="margin-right: 4px;"></i>{}</span>',
            badge_class.replace('badge ', ''),  # Убираем 'badge' для кастомного стиля
            description,  # Добавляем описание в title для tooltip
            icon,
            status_text
        )
    
    status_display.short_description = 'Статус'
    status_display.admin_order_field = 'status'
    
    def get_queryset(self, request):
        """Оптимизируем запросы для админки"""
        return super().get_queryset(request).select_related('team')
    
    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }
        js = ('js/admin_custom.js',)


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    # Показывает название, проект, статус и ответственного.
    list_display = ('title', 'project', 'status', 'assignee')
    # Добавляет фильтры.
    list_filter = ('status', 'project__team', 'project')
    # Добавляет поиск по названию.
    search_fields = ('title',)
    # Включает удобный поиск для полей с ForeignKey.
    autocomplete_fields = ('project', 'assignee')