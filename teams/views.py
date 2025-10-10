from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.views.generic import ListView, DetailView, CreateView, View
from django.shortcuts import get_object_or_404, redirect
from django.db import transaction
from django.contrib import messages
from .models import Team, TeamMembership, TeamStatusHistory, TeamStatus, ensure_leader_role_exists
from .utils import deactivate_team, reactivate_team, disband_team, can_perform_team_action
from django import forms
import logging
import json

app_name = "teams"


class TeamForm(forms.ModelForm):
    """Форма создания команды с валидацией данных"""

    class Meta:
        model = Team
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Название команды",
                    "maxlength": "100",
                }
            )
        }

    def clean_name(self):
        """Валидация поля названия команды"""
        name = self.cleaned_data.get("name")

        if not name or len(name.strip()) < 3:
            raise forms.ValidationError(
                "Название команды должно содержать минимум 3 символа"
            )

        if len(name) > 100:
            raise forms.ValidationError(
                "Название команды не может быть длиннее 100 символов"
            )

        # Проверка допустимых символов
        if not name.replace(" ", "").replace("-", "").replace("_", "").isalnum():
            raise forms.ValidationError(
                "Название может содержать только буквы, цифры, пробелы, дефисы и подчеркивания"
            )

        return name.strip()


class TeamCreateView(LoginRequiredMixin, CreateView):
    """Представление для создания новых команд"""

    model = Team
    form_class = TeamForm
    template_name = "teams/team_form.html"

    def get_form(self, form_class=None):
        """Передача текущего пользователя в форму для дополнительной валидации"""
        form = super().get_form(form_class)
        form.user = self.request.user
        return form

    @transaction.atomic
    def form_valid(self, form):
        """
        Обработка валидной формы создания команды с автоматическим назначением роли руководителя.
        
        Выполняет следующие действия:
        1. Проверяет уникальность названия команды для пользователя
        2. Создает команду с текущим пользователем как создателем
        3. Автоматически создает TeamMembership для создателя
        4. Назначает роль "Руководитель" создателю команды
        
        Все операции выполняются в рамках одной транзакции для обеспечения целостности данных.
        """
        logger = logging.getLogger(__name__)
        
        try:
            # Проверка уникальности названия команды для пользователя
            if Team.objects.filter(
                name=form.cleaned_data["name"], creator=self.request.user
            ).exists():
                form.add_error("name", "У вас уже есть команда с таким названием")
                return self.form_invalid(form)

            # Установка текущего пользователя как создателя команды
            form.instance.creator = self.request.user
            
            # Создание команды
            response = super().form_valid(form)
            
            # Создание роли "Руководитель" если она не существует
            leader_role = ensure_leader_role_exists()
            
            # Создание TeamMembership для создателя команды
            membership, created = TeamMembership.objects.get_or_create(
                user=self.request.user,
                team=self.object
            )
            
            # Назначение роли "Руководитель" создателю команды
            membership.roles.add(leader_role)
            
            # Логирование успешного создания команды
            logger.info(
                f'Команда "{self.object.name}" успешно создана пользователем {self.request.user.username}. '
                f'Создатель назначен руководителем команды.'
            )
            
            # Добавление сообщения об успехе для пользователя
            messages.success(
                self.request, 
                f'Команда "{self.object.name}" успешно создана! Вы назначены руководителем команды.'
            )
            
            return response
            
        except Exception as e:
            # Логирование ошибки
            logger.error(
                f'Ошибка при создании команды "{form.cleaned_data.get("name", "неизвестно")}" '
                f'пользователем {self.request.user.username}: {str(e)}'
            )
            
            # Добавление сообщения об ошибке для пользователя
            messages.error(
                self.request, 
                'Произошла ошибка при создании команды. Попробуйте еще раз.'
            )
            
            # Повторное возбуждение исключения для отката транзакции
            raise

    def get_success_url(self):
        # Добавляем параметры для показа модального окна успеха
        return reverse_lazy("teams:team_detail", kwargs={"pk": self.object.pk}) + \
               f"?success=created&team_name={self.object.name}&team_id={self.object.pk}"


class TeamDetailView(LoginRequiredMixin, DetailView):
    """
    Отображение детальной страницы команды со списком проектов.
    Доступ ограничен участниками команды и создателем.
    """

    model = Team
    template_name = "teams/team_detail.html"
    context_object_name = "team"

    def get_queryset(self):
        """
        Фильтрация queryset для отображения только команд,
        где пользователь является участником или создателем
        """
        return Team.objects.filter(
            Q(members=self.request.user) | Q(creator=self.request.user)
        ).distinct()

    def get_context_data(self, **kwargs):
        """
        Добавление информации об участниках команды и их ролях в контекст шаблона.
        Также определяет права текущего пользователя для отображения элементов управления.
        """
        context = super().get_context_data(**kwargs)
        team = self.get_object()
        
        # Добавление проектов команды
        context["projects"] = team.projects.all().order_by("-created_at")
        
        # Получение всех участников команды с их ролями (оптимизированный запрос)
        # Фильтруем участников по активности для неактивных команд
        if team.is_active():
            memberships = TeamMembership.objects.filter(team=team, is_active=True)
        else:
            memberships = TeamMembership.objects.filter(team=team)
        
        memberships = memberships.select_related('user')\
            .prefetch_related('roles')\
            .order_by('user__username')
        context['memberships'] = memberships
        
        # Определение прав текущего пользователя
        context['is_creator'] = team.creator == self.request.user
        
        # Получение информации о членстве текущего пользователя
        context['user_membership'] = memberships.filter(user=self.request.user).first()
        
        # Добавляем информацию о статусе команды для управления
        context['can_manage_team'] = team.can_be_managed_by(self.request.user)
        context['team_status_display'] = team.get_status_display()
        context['can_deactivate'] = team.status == TeamStatus.ACTIVE
        context['can_reactivate'] = team.status == TeamStatus.INACTIVE
        context['can_disband'] = team.status in [TeamStatus.ACTIVE, TeamStatus.INACTIVE]
        
        # Последние изменения статуса для отображения в карточке
        context['recent_status_changes'] = team.status_history.select_related('changed_by')[:5]
        
        return context


class TeamListView(LoginRequiredMixin, ListView):
    """
    Отображение списка команд пользователя с фильтрацией по статусу
    """
    model = Team
    template_name = "teams/team_list.html"
    context_object_name = "teams"
    paginate_by = 10

    def get_queryset(self):
        """
        Возвращает команды, где пользователь является участником или создателем.
        Поддерживает фильтрацию по статусу команды.
        """
        queryset = Team.objects.filter(
            Q(members=self.request.user) | Q(creator=self.request.user)
        ).distinct()
        
        # Добавляем фильтрацию по статусу
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter in [choice[0] for choice in TeamStatus.choices]:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('-updated_at')
    
    def get_context_data(self, **kwargs):
        """
        Добавляет статистику по статусам команд в контекст.
        """
        context = super().get_context_data(**kwargs)
        
        # Добавляем статистику по статусам для текущего пользователя
        user_teams = Team.objects.filter(
            Q(members=self.request.user) | Q(creator=self.request.user)
        ).distinct()
        
        context['status_counts'] = {
            'active': user_teams.filter(status=TeamStatus.ACTIVE).count(),
            'inactive': user_teams.filter(status=TeamStatus.INACTIVE).count(),
            'disbanded': user_teams.filter(status=TeamStatus.DISBANDED).count(),
        }
        
        context['current_status_filter'] = self.request.GET.get('status', 'all')
        
        # Добавляем отладочную информацию в режиме DEBUG
        from django.conf import settings
        if settings.DEBUG:
            context['debug'] = True
        
        return context


class TeamStatusChangeView(LoginRequiredMixin, View):
    """
    Представление для изменения статуса команды.
    Обрабатывает POST запросы для деактивации, реактивации и роспуска команд.
    """
    
    def get_team(self, team_id):
        """
        Получает команду и проверяет права доступа пользователя.
        
        Args:
            team_id: ID команды
            
        Returns:
            Team: Объект команды
            
        Raises:
            Http404: Если команда не найдена или нет прав доступа
        """
        team = get_object_or_404(Team, pk=team_id)
        if not team.can_be_managed_by(self.request.user):
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Пользователь {self.request.user.username} попытался получить доступ "
                f"к управлению командой {team.name} без соответствующих прав"
            )
            raise Http404("Команда не найдена")
        return team
    
    def post(self, request, team_id):
        """
        Обрабатывает POST запросы для изменения статуса команды.
        Поддерживает как обычные HTTP запросы, так и AJAX запросы.
        
        Поддерживаемые действия:
        - deactivate: приостановка команды
        - reactivate: возобновление команды  
        - disband: роспуск команды
        
        Args:
            request: HTTP запрос
            team_id: ID команды
            
        Returns:
            HttpResponse: Редирект на страницу команды или JSON ответ для AJAX
        """
        logger = logging.getLogger(__name__)
        team = self.get_team(team_id)
        action = request.POST.get('action')
        reason = request.POST.get('reason', '').strip()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Валидация действия
        if not action or action not in ['deactivate', 'reactivate', 'disband']:
            error_msg = 'Неизвестное действие. Попробуйте еще раз.'
            logger.warning(f"Получено неизвестное действие '{action}' для команды {team.name}")
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                })
            else:
                messages.error(request, error_msg)
                return redirect('teams:team_detail', pk=team_id)
        
        # Проверка возможности выполнения действия
        can_perform, error_message = can_perform_team_action(team, request.user, action)
        if not can_perform:
            logger.warning(
                f"Пользователь {request.user.username} не может выполнить действие '{action}' "
                f"для команды {team.name}: {error_message}"
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            else:
                messages.error(request, error_message)
                return redirect('teams:team_detail', pk=team_id)
        
        try:
            # Выполнение действия
            success_message = ''
            if action == 'deactivate':
                deactivate_team(team, request.user, reason)
                success_message = f'Команда "{team.name}" успешно приостановлена. Участники уведомлены об изменении статуса.'
                logger.info(f"Команда {team.name} приостановлена пользователем {request.user.username}")
                
            elif action == 'reactivate':
                reactivate_team(team, request.user, reason)
                success_message = f'Команда "{team.name}" успешно возобновлена. Все участники снова активны.'
                logger.info(f"Команда {team.name} возобновлена пользователем {request.user.username}")
                
            elif action == 'disband':
                disband_team(team, request.user, reason)
                success_message = f'Команда "{team.name}" распущена. Все участники исключены из команды.'
                logger.info(f"Команда {team.name} распущена пользователем {request.user.username}")
            
            # Обновляем объект команды из базы данных
            team.refresh_from_db()
            
            if is_ajax:
                # Получаем обновленную историю изменений для AJAX ответа
                recent_changes = team.status_history.select_related('changed_by')[:5]
                
                return JsonResponse({
                    'success': True,
                    'message': success_message,
                    'team_status': team.status,
                    'team_status_display': team.get_status_display(),
                    'action': action,
                    'recent_changes_count': recent_changes.count()
                })
            else:
                messages.success(request, success_message)
                return redirect('teams:team_detail', pk=team_id)
        
        except (PermissionError, ValueError) as e:
            # Обработка ошибок бизнес-логики
            error_msg = f'Ошибка: {str(e)}'
            logger.error(
                f"Ошибка при выполнении действия '{action}' для команды {team.name} "
                f"пользователем {request.user.username}: {str(e)}"
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                })
            else:
                messages.error(request, error_msg)
                return redirect('teams:team_detail', pk=team_id)
        
        except Exception as e:
            # Обработка неожиданных ошибок
            error_msg = 'Произошла неожиданная ошибка. Попробуйте еще раз или обратитесь к администратору.'
            logger.error(
                f"Неожиданная ошибка при выполнении действия '{action}' для команды {team.name} "
                f"пользователем {request.user.username}: {str(e)}", 
                exc_info=True
            )
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                })
            else:
                messages.error(request, error_msg)
                return redirect('teams:team_detail', pk=team_id)
    
    def get(self, request, team_id):
        """
        Обрабатывает GET запросы - перенаправляет на страницу команды.
        
        Args:
            request: HTTP запрос
            team_id: ID команды
            
        Returns:
            HttpResponse: Редирект на страницу команды
        """
        # Проверяем доступ к команде
        self.get_team(team_id)
        return redirect('teams:team_detail', pk=team_id)


class TeamCountsView(LoginRequiredMixin, View):
    """
    AJAX представление для получения счетчиков команд пользователя.
    Возвращает JSON с количеством команд по статусам.
    """
    
    def get(self, request):
        """
        Возвращает счетчики команд пользователя в формате JSON.
        
        Returns:
            JsonResponse: Словарь с количеством команд по статусам
        """
        user_teams = Team.objects.filter(
            Q(members=request.user) | Q(creator=request.user)
        ).distinct()
        
        counts = {
            'active': user_teams.filter(status=TeamStatus.ACTIVE).count(),
            'inactive': user_teams.filter(status=TeamStatus.INACTIVE).count(),
            'disbanded': user_teams.filter(status=TeamStatus.DISBANDED).count(),
        }
        
        return JsonResponse(counts)


class TeamStatusHistoryView(LoginRequiredMixin, DetailView):
    """
    Представление для просмотра истории изменений статуса команды.
    Доступно участникам команды и создателю.
    """
    model = Team
    template_name = 'teams/team_status_history.html'
    context_object_name = 'team'
    
    def get_queryset(self):
        """
        Ограничиваем доступ к командам, где пользователь является участником или создателем.
        
        Returns:
            QuerySet: Отфильтрованный queryset команд
        """
        return Team.objects.filter(
            Q(members=self.request.user) | Q(creator=self.request.user)
        ).distinct()
    
    def get_object(self, queryset=None):
        """
        Получает объект команды с дополнительной проверкой доступа.
        
        Args:
            queryset: Queryset для поиска объекта
            
        Returns:
            Team: Объект команды
            
        Raises:
            Http404: Если команда не найдена или нет доступа
        """
        obj = super().get_object(queryset)
        logger = logging.getLogger(__name__)
        logger.info(
            f"Пользователь {self.request.user.username} просматривает историю команды {obj.name}"
        )
        return obj
    
    def get_context_data(self, **kwargs):
        """
        Добавляет историю изменений статуса в контекст шаблона.
        
        Args:
            **kwargs: Дополнительные аргументы контекста
            
        Returns:
            dict: Контекст для шаблона
        """
        context = super().get_context_data(**kwargs)
        team = self.get_object()
        
        # Получаем историю изменений с оптимизированным запросом
        status_history = team.status_history.select_related('changed_by').all()[:50]
        context['status_history'] = status_history
        
        # Добавляем информацию о правах пользователя
        context['can_manage_team'] = team.can_be_managed_by(self.request.user)
        
        # Добавляем статистику изменений
        if status_history:
            context['total_changes'] = team.status_history.count()
            context['first_change'] = team.status_history.last()
            context['last_change'] = team.status_history.first()
        else:
            context['total_changes'] = 0
            context['first_change'] = None
            context['last_change'] = None
        
        return context
