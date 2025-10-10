# teams/admin.py

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

# Импортируются все модели из файла models.py этого приложения.
from .models import Role, Team, TeamMembership, TeamStatusHistory, TeamStatus
from .utils import deactivate_team, reactivate_team, disband_team

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
    autocomplete_fields = ["user"]


# Декоратор @admin.register - это современный способ регистрации модели
# с кастомным классом настроек (TeamAdmin).
@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    # Определяет, какие поля модели Team будут отображаться в виде колонок
    # в общем списке команд.
    list_display = ("name", "creator", "status_display", "member_count", "created_at", "delete_team_button")
    # Добавляет поле поиска, которое будет искать по названию команды.
    search_fields = ("name", "creator__username")
    # Добавляем фильтры по статусу и дате создания
    list_filter = ("status", "created_at", "updated_at")
    # Подключает встраиваемый редактор. Теперь на странице редактирования
    # одной команды появится таблица для управления ее участниками.
    inlines = (TeamMembershipInline,)
    # Добавляем кастомные действия для удаления и управления статусом
    actions = [
        "delete_selected_teams_with_confirmation",
        "deactivate_selected_teams",
        "reactivate_selected_teams", 
        "disband_selected_teams"
    ]

    def get_urls(self):
        """Добавляем кастомные URL для подтверждения удаления"""
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:team_id>/delete-confirm/",
                self.admin_site.admin_view(self.delete_team_confirm_view),
                name="teams_team_delete_confirm",
            ),
        ]
        return custom_urls + urls

    def status_display(self, obj):
        """Отображение статуса команды с цветовой индикацией"""
        status_colors = {
            TeamStatus.ACTIVE: '#28a745',    # Bootstrap success green
            TeamStatus.INACTIVE: '#ffc107',  # Bootstrap warning yellow
            TeamStatus.DISBANDED: '#dc3545'  # Bootstrap danger red
        }
        status_icons = {
            TeamStatus.ACTIVE: '✓',
            TeamStatus.INACTIVE: '⏸',
            TeamStatus.DISBANDED: '✗'
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        icon = status_icons.get(obj.status, '?')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )
    status_display.short_description = _("Статус")
    status_display.admin_order_field = 'status'

    def member_count(self, obj):
        """Показывает количество участников в команде"""
        count = obj.members.count()
        active_count = obj.members.filter(teammembership__is_active=True).count()
        
        if obj.status == TeamStatus.ACTIVE:
            return ngettext(
                "%(count)d участник",
                "%(count)d участников", 
                count
            ) % {'count': count}
        else:
            return format_html(
                '{} <small style="color: #6c757d;">(активных: {})</small>',
                ngettext(
                    "%(count)d участник",
                    "%(count)d участников", 
                    count
                ) % {'count': count},
                active_count
            )

    member_count.short_description = _("Участники")

    def delete_team_button(self, obj):
        """Добавляет кнопку удаления с подтверждением для каждой команды"""
        url = reverse("admin:teams_team_delete_confirm", args=[obj.pk])
        return format_html(
            '<a class="button delete-team-btn" href="{}" '
            'style="background-color: #dc3545; color: white; '
            'padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 12px; '
            'border: 1px solid #dc3545; display: inline-block;">'
            '{}</a>'
            '<style>'
            '.delete-team-btn:hover {{ '
            'background-color: #c82333 !important; '
            'border-color: #bd2130 !important; '
            'color: white !important; '
            'text-decoration: none !important; '
            '}}'
            '</style>',
            url,
            _("Удалить"),
        )

    delete_team_button.short_description = _("Действия")
    delete_team_button.allow_tags = True

    def deactivate_selected_teams(self, request, queryset):
        """Массовая приостановка команд"""
        if not request.user.is_superuser:
            self.message_user(request, _("Недостаточно прав для выполнения этого действия"), level=messages.ERROR)
            return
            
        count = 0
        errors = []
        
        for team in queryset.filter(status=TeamStatus.ACTIVE):
            try:
                deactivate_team(team, request.user, "Массовая приостановка через админку")
                count += 1
            except Exception as e:
                errors.append(f"{team.name}: {str(e)}")
        
        if count > 0:
            self.message_user(
                request, 
                ngettext(
                    "Приостановлена %(count)d команда",
                    "Приостановлено %(count)d команд",
                    count
                ) % {'count': count}
            )
        
        if errors:
            self.message_user(
                request, 
                _("Ошибки при приостановке: ") + "; ".join(errors), 
                level=messages.WARNING
            )
    
    deactivate_selected_teams.short_description = _("Приостановить выбранные команды")

    def reactivate_selected_teams(self, request, queryset):
        """Массовое возобновление команд"""
        if not request.user.is_superuser:
            self.message_user(request, _("Недостаточно прав для выполнения этого действия"), level=messages.ERROR)
            return
            
        count = 0
        errors = []
        
        for team in queryset.filter(status=TeamStatus.INACTIVE):
            try:
                reactivate_team(team, request.user, "Массовое возобновление через админку")
                count += 1
            except Exception as e:
                errors.append(f"{team.name}: {str(e)}")
        
        if count > 0:
            self.message_user(
                request, 
                ngettext(
                    "Возобновлена %(count)d команда",
                    "Возобновлено %(count)d команд",
                    count
                ) % {'count': count}
            )
        
        if errors:
            self.message_user(
                request, 
                _("Ошибки при возобновлении: ") + "; ".join(errors), 
                level=messages.WARNING
            )
    
    reactivate_selected_teams.short_description = _("Возобновить выбранные команды")

    def disband_selected_teams(self, request, queryset):
        """Массовый роспуск команд"""
        if not request.user.is_superuser:
            self.message_user(request, _("Недостаточно прав для выполнения этого действия"), level=messages.ERROR)
            return
            
        count = 0
        errors = []
        
        for team in queryset.exclude(status=TeamStatus.DISBANDED):
            try:
                disband_team(team, request.user, "Массовый роспуск через админку")
                count += 1
            except Exception as e:
                errors.append(f"{team.name}: {str(e)}")
        
        if count > 0:
            self.message_user(
                request, 
                ngettext(
                    "Распущена %(count)d команда",
                    "Распущено %(count)d команд",
                    count
                ) % {'count': count}
            )
        
        if errors:
            self.message_user(
                request, 
                _("Ошибки при роспуске: ") + "; ".join(errors), 
                level=messages.WARNING
            )
    
    disband_selected_teams.short_description = _("Распустить выбранные команды")

    def delete_team_confirm_view(self, request, team_id):
        """Страница подтверждения удаления команды"""
        try:
            team = Team.objects.get(pk=team_id)
        except Team.DoesNotExist:
            messages.error(request, _("Команда с ID %(team_id)s не найдена.") % {'team_id': team_id})
            return HttpResponseRedirect(reverse("admin:teams_team_changelist"))

        if request.method == "POST":
            if "confirm" in request.POST:
                # Получаем информацию о команде для логирования
                team_name = team.name
                creator_name = team.creator.username
                member_count = team.members.count()

                # Удаляем команду
                team.delete()

                messages.success(
                    request,
                    _('Команда "%(team_name)s" (создатель: %(creator_name)s, участников: %(member_count)d) успешно удалена.') % {
                        'team_name': team_name,
                        'creator_name': creator_name,
                        'member_count': member_count
                    }
                )

                return HttpResponseRedirect(reverse("admin:teams_team_changelist"))
            else:
                # Пользователь отменил удаление
                messages.info(request, _('Удаление команды "%(team_name)s" отменено.') % {'team_name': team.name})
                return HttpResponseRedirect(reverse("admin:teams_team_changelist"))

        # Получаем дополнительную информацию о команде для отображения
        context = {
            "team": team,
            "member_count": team.members.count(),
            "active_member_count": team.members.filter(teammembership__is_active=True).count(),
            "memberships": TeamMembership.objects.filter(team=team)
            .select_related("user")
            .prefetch_related("roles"),
            "recent_status_changes": team.status_history.select_related('changed_by')[:5],
            "title": _('Подтверждение удаления команды "%(team_name)s"') % {'team_name': team.name},
            "opts": self.model._meta,
            "has_view_permission": self.has_view_permission(request),
        }

        return render(request, "admin/teams/team/delete_confirmation.html", context)

    def delete_selected_teams_with_confirmation(self, request, queryset):
        """Массовое удаление команд с подтверждением"""
        if request.POST.get("post"):
            # Подтверждение получено, удаляем команды
            count = queryset.count()
            team_names = list(queryset.values_list("name", flat=True))
            queryset.delete()

            messages.success(
                request,
                ngettext(
                    "Успешно удалена %(count)d команда. Удаленная команда: %(team_names)s",
                    "Успешно удалено %(count)d команд. Удаленные команды: %(team_names)s",
                    count
                ) % {
                    'count': count,
                    'team_names': ", ".join(team_names)
                }
            )
            return HttpResponseRedirect(request.get_full_path())

        # Показываем страницу подтверждения
        context = {
            "teams": queryset,
            "team_count": queryset.count(),
            "total_members": sum(team.members.count() for team in queryset),
            "title": _("Подтверждение удаления команд"),
            "opts": self.model._meta,
            "action_checkbox_name": admin.ACTION_CHECKBOX_NAME,
            "queryset": queryset,
        }

        return render(
            request, "admin/teams/team/delete_selected_confirmation.html", context
        )

    delete_selected_teams_with_confirmation.short_description = _(
        "Удалить выбранные команды (с подтверждением)"
    )

    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только через наши кастомные методы"""
        return request.user.is_superuser


# Отдельная регистрация модели TeamMembership для более детального управления.
@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    # Определяет колонки в общем списке всех "членств в командах".
    list_display = ("user", "team", "is_active_display", "joined_at")
    # Добавляет боковую панель для фильтрации по команде и активности.
    list_filter = ("team", "is_active", "joined_at")
    # Включает виджет с поиском для полей 'user' и 'team'.
    autocomplete_fields = ["user", "team"]
    # Добавляем поиск по пользователю
    search_fields = ("user__username", "team__name")
    # Сортировка по умолчанию
    ordering = ("-joined_at",)

    def is_active_display(self, obj):
        """Отображение статуса активности участника"""
        if obj.is_active:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Активен</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✗ Неактивен</span>'
            )
    is_active_display.short_description = _("Статус")
    is_active_display.admin_order_field = 'is_active'


@admin.register(TeamStatusHistory)
class TeamStatusHistoryAdmin(admin.ModelAdmin):
    """Админка для истории изменений статуса команд"""
    list_display = ("team", "change_type_display", "status_change", "changed_by", "timestamp")
    list_filter = ("change_type", "new_status", "timestamp")
    search_fields = ("team__name", "changed_by__username", "reason")
    readonly_fields = ("team", "changed_by", "change_type", "old_status", "new_status", "reason", "timestamp")
    ordering = ("-timestamp",)
    
    def has_add_permission(self, request):
        """Запрещаем создание записей вручную"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление записей истории"""
        return False
    
    def change_type_display(self, obj):
        """Отображение типа изменения с иконкой"""
        icons = {
            'created': '➕',
            'deactivated': '⏸',
            'reactivated': '▶️',
            'disbanded': '❌'
        }
        colors = {
            'created': '#28a745',
            'deactivated': '#ffc107', 
            'reactivated': '#17a2b8',
            'disbanded': '#dc3545'
        }
        
        icon = icons.get(obj.change_type, '?')
        color = colors.get(obj.change_type, '#6c757d')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_change_type_display()
        )
    change_type_display.short_description = _("Действие")
    change_type_display.admin_order_field = 'change_type'
    
    def status_change(self, obj):
        """Отображение изменения статуса"""
        if obj.old_status:
            return format_html(
                '<span style="color: #6c757d;">{}</span> → <span style="color: #007cba; font-weight: bold;">{}</span>',
                obj.get_old_status_display(),
                obj.get_new_status_display()
            )
        else:
            return format_html(
                '<span style="color: #007cba; font-weight: bold;">{}</span>',
                obj.get_new_status_display()
            )
    status_change.short_description = _("Изменение статуса")
    
    def get_queryset(self, request):
        """Оптимизируем запросы"""
        return super().get_queryset(request).select_related('team', 'changed_by')
