# projects/admin.py

from django.contrib import admin
from .models import Project, Chapter

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    # Показывает название, команду и статус в списке проектов.
    list_display = ('title', 'team', 'status')
    # Добавляет фильтр по статусу и команде.
    list_filter = ('status', 'team')
    # Добавляет поле поиска по названию.
    search_fields = ('title',)

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