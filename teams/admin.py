# teams/admin.py

from django.contrib import admin
# Импортируются все модели из файла models.py этого приложения.
from .models import Role, Team, TeamMembership

# Простая регистрация модели Role. Она появится в админке как отдельный раздел.
admin.site.register(Role)


# Этот класс описывает "встраиваемый" редактор.
# Он позволит управлять участниками (TeamMembership) прямо со страницы команды (Team).
class TeamMembershipInline(admin.TabularInline):
    # Указывается, что этот редактор предназначен для модели TeamMembership.
    model = TeamMembership
    # По умолчанию будет отображаться одно пустое поле для добавления нового участника.
    extra = 1
    # Для поля 'user' будет использоваться удобный виджет с поиском,
    # а не гигантский выпадающий список.
    autocomplete_fields = ['user']


# Декоратор @admin.register - это современный способ регистрации модели
# с кастомным классом настроек (TeamAdmin).
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    # Определяет, какие поля модели Team будут отображаться в виде колонок
    # в общем списке команд.
    list_display = ('name', 'creator')
    # Добавляет поле поиска, которое будет искать по названию команды.
    search_fields = ('name',)
    # Подключает встраиваемый редактор. Теперь на странице редактирования
    # одной команды появится таблица для управления ее участниками.
    inlines = (TeamMembershipInline,)


# Отдельная регистрация модели TeamMembership для более детального управления.
@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    # Определяет колонки в общем списке всех "членств в командах".
    list_display = ('user', 'team')
    # Добавляет боковую панель для фильтрации по команде.
    list_filter = ('team',)
    # Включает виджет с поиском для полей 'user' и 'team'.
    autocomplete_fields = ['user', 'team']