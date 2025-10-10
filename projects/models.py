# projects/models.py

from django.db import models
# Импортируем модель Team, чтобы связать проекты с командами.
from teams.models import Team
# Импортируем модель User, чтобы назначать ответственных.
from django.conf import settings


class Project(models.Model):
    """
    Модель для проекта перевода (тайтла манги, книги и т.д.).
    """
    # Связь "один-ко-многим" с моделью Team.
    # on_delete=models.CASCADE означает, что если команда будет удалена,
    # все ее проекты также будут удалены.
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects')
    # Название проекта.
    title = models.CharField(max_length=200)
    # Опциональное описание.
    description = models.TextField(blank=True)
    # Статусы проекта для отслеживания (например, активен, завершен, заброшен).
    STATUS_CHOICES = (
        ('active', 'Активен'),
        ('completed', 'Завершен'),
        ('on_hold', 'В заморозке'),
        ('dropped', 'Заброшен'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    # Дата создания проекта, заполняется автоматически.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Возвращает название проекта в виде строки (удобно для админки).
        return self.title


class Chapter(models.Model):
    """
    Модель для отдельной главы, основной единицы работы.
    """
    # Связь с проектом. Если проект удаляется, удаляются и все его главы.
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chapters')
    # Название главы (например, "Глава 1: Начало").
    title = models.CharField(max_length=200)
    # Ответственный за текущий этап работы. Может быть не назначен.
    # on_delete=models.SET_NULL означает, что если пользователь будет удален,
    # поле assignee в главе просто станет пустым (NULL), а сама глава не удалится.
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )
    # Статусы для Kanban-доски.
    STATUS_CHOICES = (
        ('raw', 'RAW'),
        ('translating', 'Перевод'),
        ('cleaning', 'Клининг'),
        ('typesetting', 'Тайпинг'),
        ('editing', 'Редактура'),
        ('done', 'Готово'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='raw')
    # Дата создания главы, заполняется автоматически.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project.title} - {self.title}"