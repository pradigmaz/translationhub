from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import Http404
from django.views.generic import ListView, DetailView, CreateView
from .models import Team
from django import forms

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

    def form_valid(self, form):
        # Проверка уникальности названия команды для пользователя
        if Team.objects.filter(
            name=form.cleaned_data["name"], creator=self.request.user
        ).exists():
            form.add_error("name", "У вас уже есть команда с таким названием")
            return self.form_invalid(form)

        # Установка текущего пользователя как создателя команды
        form.instance.creator = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("teams:team_detail", kwargs={"pk": self.object.pk})


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
        Добавление проектов команды в контекст шаблона
        """
        context = super().get_context_data(**kwargs)
        team = self.get_object()
        context["projects"] = team.projects.all().order_by("-created_at")
        return context
