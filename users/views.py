from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.forms import UserCreationForm
from django import forms
from teams.models import Team
from projects.models import Chapter
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """
    Кастомная форма регистрации для модели User
    """

    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавление CSS классов для стилизации полей формы
        for field_name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"


class RegisterView(CreateView):
    """Представление для регистрации новых пользователей"""
    
    form_class = CustomUserCreationForm
    model = User
    template_name = "users/register.html"
    success_url = reverse_lazy("users:login")


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

        # Добавление списка команд пользователя в контекст
        context["user_teams"] = current_user.teams.all().order_by("name")

        # Добавление списка назначенных пользователю глав в контекст
        context["user_tasks"] = Chapter.objects.filter(assignee=current_user).order_by(
            "created_at"
        )

        return context
