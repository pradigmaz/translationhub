from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth import login
from django.http import HttpResponseRedirect
from django.contrib import messages
import logging
from teams.models import Team, TeamMembership
from projects.models import Chapter
from .models import User
from .forms import ProfileForm, SettingsForm, CustomPasswordChangeForm

# Настройка логгера безопасности
security_logger = logging.getLogger('security')


class CustomUserCreationForm(UserCreationForm):
    """
    Кастомная форма регистрации для модели User с дополнительной валидацией
    """

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавление CSS классов для стилизации полей формы
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            
        # Добавление подсказок для безопасности
        self.fields['username'].help_text = "Только буквы, цифры и символы @/./+/-/_"
        self.fields['password1'].help_text = "Минимум 12 символов, не должен быть слишком простым"

    def clean_username(self):
        """Дополнительная валидация имени пользователя"""
        username = self.cleaned_data.get('username')
        
        if not username:
            raise forms.ValidationError("Имя пользователя обязательно")
            
        # Проверка длины
        if len(username) < 3:
            raise forms.ValidationError("Имя пользователя должно содержать минимум 3 символа")
            
        if len(username) > 150:
            raise forms.ValidationError("Имя пользователя не может быть длиннее 150 символов")
            
        # Проверка на недопустимые символы
        import re
        if not re.match(r'^[\w.@+-]+$', username):
            raise forms.ValidationError("Имя пользователя может содержать только буквы, цифры и символы @/./+/-/_")
            
        return username


class RegisterView(CreateView):
    """Представление для регистрации новых пользователей с логированием"""
    
    form_class = CustomUserCreationForm
    model = User
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")
    
    def form_valid(self, form):
        """Обработка успешной регистрации с логированием"""
        response = super().form_valid(form)
        
        # Логирование успешной регистрации
        security_logger.info(
            f"New user registered: {form.cleaned_data['username']} from IP: {self.get_client_ip()}"
        )
        
        messages.success(
            self.request, 
            "Регистрация прошла успешно! Теперь вы можете войти в систему."
        )
        
        return response
    
    def form_invalid(self, form):
        """Обработка неудачной регистрации с логированием"""
        # Логирование неудачной попытки регистрации
        security_logger.warning(
            f"Failed registration attempt for username: {form.data.get('username', 'unknown')} "
            f"from IP: {self.get_client_ip()}, errors: {form.errors}"
        )
        
        return super().form_invalid(form)
    
    def get_client_ip(self):
        """Получение IP адреса клиента"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Отображение личного кабинета пользователя с командами и задачами
    """

    template_name = "users/dashboard.html"

    def get_context_data(self, **kwargs):
        """
        Подготовка и передача данных в шаблон
        """
        context = super().get_context_data(**kwargs)
        current_user = self.request.user

        # Добавление аватарки пользователя в контекст
        context["user_avatar"] = current_user.avatar if current_user.avatar else None

        # Добавление списка команд пользователя в контекст
        user_teams = current_user.teams.all().order_by("name")
        context["user_teams"] = user_teams
        
        # Подсчет команд
        context["teams_count"] = user_teams.count()

        # Добавление списка назначенных пользователю глав в контекст
        user_tasks = Chapter.objects.filter(assignee=current_user).order_by("-created_at")
        context["user_tasks"] = user_tasks
        
        # Подсчет задач
        context["tasks_count"] = user_tasks.count()
        
        # Последние 5 задач для отображения на дашборде
        context["recent_tasks"] = user_tasks[:5]
        
        # Подсчет проектов пользователя
        from projects.models import Project
        user_projects = Project.objects.filter(team__members=current_user)
        context["projects_count"] = user_projects.count()
        
        # Подсчет активных задач
        context["active_tasks_count"] = user_tasks.exclude(status='done').count()

        return context


class ProfileView(LoginRequiredMixin, TemplateView):
    """
    Отображение профиля пользователя
    """
    template_name = "users/profile.html"

    def get_context_data(self, **kwargs):
        """
        Подготовка данных профиля для шаблона
        """
        context = super().get_context_data(**kwargs)
        current_user = self.request.user
        
        # Статистика пользователя
        context["user_teams_count"] = current_user.teams.count()
        context["user_tasks_count"] = Chapter.objects.filter(assignee=current_user).count()
        context["completed_tasks_count"] = Chapter.objects.filter(
            assignee=current_user, 
            status='done'
        ).count()
        
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """
    Представление для редактирования профиля пользователя с аватаркой
    """
    model = User
    form_class = ProfileForm
    template_name = "users/profile_edit.html"
    success_url = reverse_lazy("users:profile")

    def get_object(self):
        """
        Возвращает текущего пользователя для редактирования
        """
        return self.request.user

    def form_valid(self, form):
        """
        Обработка успешного сохранения профиля с логированием
        """
        from utils.file_system import DirectoryManager, FileUploadError
        
        # Если загружается аватарка, создаем папку пользователя
        if form.cleaned_data.get('avatar'):
            try:
                DirectoryManager.create_user_directory(self.request.user.id)
            except FileUploadError as e:
                messages.error(self.request, f"Ошибка создания папки пользователя: {str(e)}")
                return self.form_invalid(form)
        
        response = super().form_valid(form)
        
        # Логирование изменения профиля
        security_logger.info(
            f"Profile updated for user: {self.request.user.username} "
            f"from IP: {self.get_client_ip()}"
        )
        
        messages.success(
            self.request, 
            "Профиль успешно обновлен!"
        )
        
        return response

    def form_invalid(self, form):
        """
        Обработка ошибок валидации с сообщениями пользователю
        """
        messages.error(
            self.request,
            "Пожалуйста, исправьте ошибки в форме."
        )
        return super().form_invalid(form)

    def get_client_ip(self):
        """Получение IP адреса клиента"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip


class TeamsView(LoginRequiredMixin, TemplateView):
    """
    Представление для отображения команд пользователя с ролями
    """
    template_name = "users/teams.html"

    def get_context_data(self, **kwargs):
        """
        Подготовка данных о командах пользователя для шаблона
        """
        context = super().get_context_data(**kwargs)
        current_user = self.request.user

        # Получаем все членства пользователя в командах с ролями
        team_memberships = TeamMembership.objects.filter(
            user=current_user
        ).select_related('team').prefetch_related('roles').order_by('team__name')

        context["team_memberships"] = team_memberships
        context["teams_count"] = team_memberships.count()

        return context


class TasksView(LoginRequiredMixin, TemplateView):
    """
    Представление для отображения задач пользователя
    """
    template_name = "users/tasks.html"

    def get_context_data(self, **kwargs):
        """
        Подготовка данных о задачах пользователя для шаблона
        """
        context = super().get_context_data(**kwargs)
        current_user = self.request.user

        # Получаем все назначенные пользователю задачи с информацией о проекте
        user_tasks = Chapter.objects.filter(
            assignee=current_user
        ).select_related('project').order_by('-created_at')

        context["user_tasks"] = user_tasks
        context["tasks_count"] = user_tasks.count()
        
        # Группировка задач по статусам для удобства отображения
        context["tasks_by_status"] = {
            'raw': user_tasks.filter(status='raw'),
            'translating': user_tasks.filter(status='translating'),
            'cleaning': user_tasks.filter(status='cleaning'),
            'typesetting': user_tasks.filter(status='typesetting'),
            'editing': user_tasks.filter(status='editing'),
            'done': user_tasks.filter(status='done'),
        }

        return context

class SettingsView(LoginRequiredMixin, FormView):
    """
    Представление для изменения настроек аккаунта (email и пароль)
    """
    template_name = "users/settings.html"
    form_class = SettingsForm
    success_url = reverse_lazy("users:settings")

    def get_form_kwargs(self):
        """
        Передача текущего пользователя в форму
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Добавление формы смены пароля в контекст
        """
        context = super().get_context_data(**kwargs)
        
        # Добавляем форму смены пароля
        if 'password_form' not in context:
            context['password_form'] = CustomPasswordChangeForm(user=self.request.user)
        
        return context

    def post(self, request, *args, **kwargs):
        """
        Обработка POST запросов для профиля, настроек и смены пароля
        """
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            return self.handle_profile_update(request)
        elif form_type == 'password':
            return self.handle_password_change(request)
        else:
            return super().post(request, *args, **kwargs)

    def handle_profile_update(self, request):
        """
        Обработка обновления профиля (аватарка, display_name, email)
        """
        from utils.file_system import FileUploadHandler, FileUploadError, DirectoryManager
        
        user = request.user
        
        # Обновляем поля профиля
        display_name = request.POST.get('display_name', '').strip()
        email = request.POST.get('email', '').strip()
        avatar = request.FILES.get('avatar')
        
        # Валидация email
        if email and email != user.email:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(email)
                user.email = email
            except ValidationError:
                messages.error(request, "Некорректный email адрес")
                return HttpResponseRedirect(self.success_url)
        
        # Обновляем display_name
        if display_name != user.display_name:
            user.display_name = display_name
        
        # Обновляем аватарку с использованием новой файловой системы
        if avatar:
            try:
                # Создаем папку пользователя если не существует
                DirectoryManager.create_user_directory(user.id)
                
                # Валидируем файл через FileUploadHandler
                FileUploadHandler.validate_file(
                    avatar, 
                    FileUploadHandler.ALLOWED_IMAGE_TYPES, 
                    FileUploadHandler.MAX_IMAGE_SIZE,
                    user.id
                )
                
                # Устанавливаем аватарку (путь будет сгенерирован через upload_to)
                user.avatar = avatar
                
            except FileUploadError as e:
                messages.error(request, f"Ошибка загрузки аватарки: {str(e)}")
                return HttpResponseRedirect(self.success_url)
            except Exception as e:
                messages.error(request, "Произошла ошибка при загрузке аватарки")
                return HttpResponseRedirect(self.success_url)
        
        user.save()
        
        # Логирование изменения профиля
        security_logger.info(
            f"Profile updated for user: {user.username} "
            f"from IP: {self.get_client_ip(request)}"
        )
        
        messages.success(request, "Профиль успешно обновлен!")
        return HttpResponseRedirect(self.success_url)

    def handle_password_change(self, request):
        """
        Обработка смены пароля
        """
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        
        if password_form.is_valid():
            password_form.save()
            
            # Логирование смены пароля
            security_logger.info(
                f"Password changed for user: {request.user.username} "
                f"from IP: {self.get_client_ip(request)}"
            )
            
            messages.success(request, "Пароль успешно изменен!")
            return HttpResponseRedirect(self.success_url)
        else:
            # Если форма пароля невалидна, показываем ошибки
            context = self.get_context_data()
            context['password_form'] = password_form
            return self.render_to_response(context)

    def form_valid(self, form):
        """
        Обработка успешной валидации формы email
        """
        user = self.request.user
        user.email = form.cleaned_data['email']
        user.save()
        
        # Логирование изменения настроек
        security_logger.info(
            f"Settings updated for user: {user.username} "
            f"from IP: {self.get_client_ip(self.request)}"
        )
        
        messages.success(self.request, "Настройки успешно сохранены!")
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Обработка ошибок валидации
        """
        messages.error(
            self.request,
            "Пожалуйста, исправьте ошибки в форме."
        )
        return super().form_invalid(form)

    def get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip