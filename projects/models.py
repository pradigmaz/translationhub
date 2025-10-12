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
    
    # Типы проектов для категоризации контента
    PROJECT_TYPE_CHOICES = [
        ('manga', 'Манга'),
        ('manhwa', 'Манхва'),
        ('manhua', 'Маньхуа'),
    ]
    project_type = models.CharField(
        max_length=10, 
        choices=PROJECT_TYPE_CHOICES, 
        default='manga',
        verbose_name="Тип проекта"
    )
    
    # Возрастные рейтинги для контента
    AGE_RATING_CHOICES = [
        ('general', 'Обычная'),
        ('adult', '18+'),
    ]
    age_rating = models.CharField(
        max_length=10, 
        choices=AGE_RATING_CHOICES, 
        default='general',
        verbose_name="Возрастной рейтинг"
    )
    
    # Поле для автогенерированной папки контента
    # Уникальность только в рамках команды - разные команды могут иметь одинаковые папки
    content_folder = models.CharField(
        max_length=100, 
        verbose_name="Папка контента",
        blank=True  # Будет заполняться автоматически
    )
    
    # Обновленные статусы проекта для отслеживания перевода
    STATUS_CHOICES = [
        ('translating', 'Переводим'),      # Активная работа над проектом
        ('dropped', 'Заброшен'),           # Команда прекратила работу
        ('completed', 'Переведён'),        # Все главы готовы
        ('frozen', 'Заморожен'),           # Временная приостановка
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='translating',  # Новый проект по умолчанию "переводим"
        verbose_name="Статус проекта"
    )
    # Дата создания проекта, заполняется автоматически.
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Уникальность папки только в рамках команды
        unique_together = [['team', 'content_folder']]

    def get_status_badge_class(self):
        """Возвращает CSS класс для badge статуса"""
        status_classes = {
            'translating': 'bg-primary',
            'dropped': 'bg-secondary', 
            'completed': 'bg-success',
            'frozen': 'bg-warning',
        }
        return f"badge {status_classes.get(self.status, 'bg-secondary')}"

    def get_status_icon(self):
        """Возвращает иконку FontAwesome для статуса"""
        status_icons = {
            'translating': 'fas fa-language',
            'dropped': 'fas fa-stop-circle',
            'completed': 'fas fa-check-circle', 
            'frozen': 'fas fa-pause-circle',
        }
        return status_icons.get(self.status, 'fas fa-question-circle')

    def get_status_description(self):
        """Возвращает описание статуса для подсказок"""
        descriptions = {
            'translating': 'Проект активно переводится командой',
            'dropped': 'Команда прекратила работу над проектом',
            'completed': 'Все главы проекта переведены и готовы',
            'frozen': 'Работа временно приостановлена (перерыв, ожидание новых глав)',
        }
        return descriptions.get(self.status, 'Неизвестный статус')

    def user_has_access(self, user):
        """Проверяет, имеет ли пользователь доступ к проекту через активное членство в команде"""
        return (
            self.team.members.filter(
                id=user.id,
                teammembership__is_active=True
            ).exists() and 
            self.team.status == 'active'
        )
    
    def get_active_members(self):
        """Возвращает активных участников команды проекта"""
        return self.team.members.filter(
            teammembership__is_active=True
        ).select_related('teammembership')
    
    def can_be_edited_by(self, user):
        """Проверяет, может ли пользователь редактировать проект"""
        return (
            self.user_has_access(user) and 
            (self.team.creator == user or user.is_superuser)
        )

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