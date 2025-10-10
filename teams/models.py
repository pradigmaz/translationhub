from django.conf import settings
from django.db import models
import logging

# Create your models here.

logger = logging.getLogger(__name__)


class TeamStatus(models.TextChoices):
    """Возможные статусы команды"""
    ACTIVE = 'active', 'Активная'
    INACTIVE = 'inactive', 'Неактивная' 
    DISBANDED = 'disbanded', 'Распущена'


class TeamStatusChangeType(models.TextChoices):
    """Типы изменений статуса команды"""
    CREATED = 'created', 'Создана'
    DEACTIVATED = 'deactivated', 'Приостановлена'
    REACTIVATED = 'reactivated', 'Возобновлена'
    DISBANDED = 'disbanded', 'Распущена'


class Role(models.Model):
    """Модель для хранения возможных ролей (Переводчик, Клинер и т.д.)."""

    name = models.CharField(max_length=50, unique=True, help_text="Изменение роли")
    description = models.TextField(blank=True, help_text="Описание роли")

    def __str__(self):
        return self.name


class Team(models.Model):
    """Модель команды переводчиков"""

    name = models.CharField(max_length=100)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_teams"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="TeamMembership", related_name="teams"
    )
    
    # Новые поля для управления жизненным циклом
    status = models.CharField(
        max_length=20,
        choices=TeamStatus.choices,
        default=TeamStatus.ACTIVE,
        help_text="Текущий статус команды"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['creator', 'status']),
        ]
    
    def can_be_managed_by(self, user):
        """Проверяет, может ли пользователь управлять командой"""
        return self.creator == user or user.is_superuser
    
    def is_active(self):
        """Проверяет, активна ли команда"""
        return self.status == TeamStatus.ACTIVE
    
    def can_be_reactivated(self):
        """Проверяет, может ли команда быть возобновлена"""
        return self.status == TeamStatus.INACTIVE
    
    def can_be_disbanded(self):
        """Проверяет, может ли команда быть распущена"""
        return self.status in [TeamStatus.ACTIVE, TeamStatus.INACTIVE]

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    """
    Промежуточная модель, которая связывает Пользователя и Команду.
    Именно она позволяет нам добавить дополнительные данные к этой связи,
    а именно - РОЛИ.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    roles = models.ManyToManyField(Role)
    
    # Новые поля для отслеживания активности
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Активен ли участник в команде"
    )

    class Meta:
        unique_together = ("user", "team")
        indexes = [
            models.Index(fields=['team', 'is_active']),
        ]
    
    def deactivate(self):
        """Деактивирует участника команды"""
        self.is_active = False
        self.save()
    
    def reactivate(self):
        """Реактивирует участника команды"""
        self.is_active = True
        self.save()

    def __str__(self):
        role_names = ", ".join([role.name for role in self.roles.all()])
        return f"{self.user.username} в команде {self.team.name} как {role_names}"


class TeamStatusHistory(models.Model):
    """История изменений статуса команды для аудита"""
    team = models.ForeignKey(
        Team, 
        on_delete=models.CASCADE, 
        related_name='status_history'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='team_status_changes'
    )
    change_type = models.CharField(
        max_length=20,
        choices=TeamStatusChangeType.choices
    )
    old_status = models.CharField(
        max_length=20,
        choices=TeamStatus.choices,
        null=True,
        blank=True
    )
    new_status = models.CharField(
        max_length=20,
        choices=TeamStatus.choices
    )
    reason = models.TextField(
        blank=True,
        help_text="Причина изменения статуса"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['team', '-timestamp']),
            models.Index(fields=['changed_by', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.team.name}: {self.get_change_type_display()} ({self.timestamp})"


def ensure_leader_role_exists():
    """
    Создает роль "Руководитель" если она не существует в системе.

    Returns:
        Role: Объект роли "Руководитель"

    Raises:
        Exception: При ошибке создания или получения роли
    """
    try:
        role, created = Role.objects.get_or_create(
            name="Руководитель",
            defaults={
                "description": "Руководитель команды с полными правами управления"
            },
        )

        if created:
            logger.info(f"Создана новая роль: {role.name}")
        else:
            logger.debug(f"Роль уже существует: {role.name}")

        return role

    except Exception as e:
        logger.error(f'Ошибка при создании/получении роли "Руководитель": {str(e)}')
        raise Exception(f'Не удалось создать роль "Руководитель": {str(e)}')


# Утилитные функции для управления статусом команды находятся в teams/utils.py
# Доступные функции:
# - deactivate_team(team, user, reason="")
# - reactivate_team(team, user, reason="")  
# - disband_team(team, user, reason="")
# - get_team_status_statistics(user=None)
# - can_perform_team_action(team, user, action)
