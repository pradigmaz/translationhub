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

    name = models.CharField(max_length=50, unique=True, verbose_name="Название роли")
    description = models.TextField(blank=True, verbose_name="Описание роли")
    permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='roles',
        verbose_name="Разрешения",
        help_text="Разрешения, назначенные этой роли"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="Стандартная роль",
        help_text="Является ли роль стандартной (создается автоматически)"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создана")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлена")

    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
        ordering = ['name']
        permissions = [
            # Разрешения для команд
            ("can_manage_team", "Может управлять командой"),
            ("can_invite_members", "Может приглашать участников"),
            ("can_remove_members", "Может удалять участников"),
            ("can_assign_roles", "Может назначать роли"),
            ("can_change_team_status", "Может изменять статус команды"),
            
            # Разрешения для проектов
            ("can_create_project", "Может создавать проекты"),
            ("can_manage_project", "Может управлять проектами"),
            ("can_delete_project", "Может удалять проекты"),
            ("can_assign_chapters", "Может назначать главы"),
            
            # Разрешения для контента
            ("can_edit_content", "Может редактировать контент"),
            ("can_review_content", "Может рецензировать контент"),
            ("can_publish_content", "Может публиковать контент"),
        ]

    def get_permission_names(self):
        """Возвращает список названий разрешений"""
        return list(self.permissions.values_list('codename', flat=True))
        
    def has_permission(self, permission_codename):
        """Проверяет наличие конкретного разрешения"""
        return self.permissions.filter(codename=permission_codename).exists()
    
    def add_permission(self, permission_codename):
        """Добавляет разрешение к роли"""
        from django.contrib.auth.models import Permission
        try:
            permission = Permission.objects.get(codename=permission_codename)
            self.permissions.add(permission)
            return True
        except Permission.DoesNotExist:
            return False
    
    def remove_permission(self, permission_codename):
        """Удаляет разрешение из роли"""
        from django.contrib.auth.models import Permission
        try:
            permission = Permission.objects.get(codename=permission_codename)
            self.permissions.remove(permission)
            return True
        except Permission.DoesNotExist:
            return False
    
    def get_permission_count(self):
        """Возвращает количество разрешений у роли"""
        return self.permissions.count()
    
    def get_usage_count(self):
        """Возвращает количество использований роли (участников с этой ролью)"""
        return TeamMembership.objects.filter(roles=self).count()
    
    def save(self, *args, **kwargs):
        """Переопределяем save для логирования изменений"""
        from .audit_logger import RoleAuditLogger
        
        # Определяем, создается ли новая роль или обновляется существующая
        is_new = self.pk is None
        
        # Если это обновление, получаем старые значения для сравнения
        old_instance = None
        if not is_new:
            try:
                old_instance = Role.objects.get(pk=self.pk)
            except Role.DoesNotExist:
                pass
        
        # Сохраняем объект
        super().save(*args, **kwargs)
        
        # Логируем изменения
        if is_new:
            # Логируем создание новой роли
            permissions = list(self.permissions.values_list('codename', flat=True))
            RoleAuditLogger.log_role_created(
                user=getattr(self, '_audit_user', None),
                role_name=self.name,
                description=self.description,
                permissions=permissions,
                is_default=self.is_default
            )
        elif old_instance:
            # Логируем изменения существующей роли
            changes = {}
            
            if old_instance.name != self.name:
                changes['name'] = (old_instance.name, self.name)
            
            if old_instance.description != self.description:
                changes['description'] = (old_instance.description, self.description)
            
            if old_instance.is_default != self.is_default:
                changes['is_default'] = (old_instance.is_default, self.is_default)
            
            # Проверяем изменения в разрешениях
            old_permissions = set(old_instance.permissions.values_list('codename', flat=True))
            new_permissions = set(self.permissions.values_list('codename', flat=True))
            
            if old_permissions != new_permissions:
                changes['permissions'] = (list(old_permissions), list(new_permissions))
            
            if changes:
                RoleAuditLogger.log_role_updated(
                    user=getattr(self, '_audit_user', None),
                    role_name=self.name,
                    changes=changes
                )
    
    def delete(self, *args, **kwargs):
        """Переопределяем delete для логирования удаления"""
        from .audit_logger import RoleAuditLogger
        
        # Сохраняем информацию перед удалением
        role_name = self.name
        usage_count = self.get_usage_count()
        permissions = list(self.permissions.values_list('codename', flat=True))
        
        # Удаляем объект
        super().delete(*args, **kwargs)
        
        # Логируем удаление
        RoleAuditLogger.log_role_deleted(
            user=getattr(self, '_audit_user', None),
            role_name=role_name,
            usage_count=usage_count,
            permissions=permissions
        )
    
    @classmethod
    def ensure_default_roles_exist(cls):
        """
        Создает стандартные роли если они не существуют.
        
        Использует DefaultRoleManager для создания стандартных ролей системы.
        
        Returns:
            dict: Результаты создания ролей
        """
        from .role_manager import DefaultRoleManager
        return DefaultRoleManager.ensure_default_roles_exist()

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """
    Модель для хранения глобальных ролей пользователей (не привязанных к командам).
    
    Используется для:
    - Назначения дефолтной роли новым пользователям
    - Отслеживания глобального статуса пользователя в системе
    - Управления базовыми разрешениями пользователя
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='global_roles',
        verbose_name="Пользователь"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='global_users',
        verbose_name="Роль"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Активна ли роль для пользователя"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Назначена"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_global_roles',
        verbose_name="Назначена пользователем"
    )
    
    class Meta:
        unique_together = ('user', 'role')
        verbose_name = "Глобальная роль пользователя"
        verbose_name_plural = "Глобальные роли пользователей"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['role', 'is_active']),
        ]
    
    def deactivate(self, deactivated_by=None):
        """Деактивирует роль пользователя"""
        self.is_active = False
        if deactivated_by:
            self.assigned_by = deactivated_by
        self.save()
    
    def reactivate(self, reactivated_by=None):
        """Реактивирует роль пользователя"""
        self.is_active = True
        if reactivated_by:
            self.assigned_by = reactivated_by
        self.save()
    
    def __str__(self):
        status = "активна" if self.is_active else "неактивна"
        return f"{self.user.username} - {self.role.name} ({status})"


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
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
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
    
    def add_role(self, role, admin_user=None):
        """Добавляет роль участнику с логированием"""
        from .audit_logger import RoleAuditLogger
        
        if role not in self.roles.all():
            self.roles.add(role)
            RoleAuditLogger.log_role_assigned_to_user(
                admin_user=admin_user,
                target_user=self.user,
                role_name=role.name,
                team_name=self.team.name
            )
    
    def remove_role(self, role, admin_user=None):
        """Удаляет роль у участника с логированием"""
        from .audit_logger import RoleAuditLogger
        
        if role in self.roles.all():
            self.roles.remove(role)
            RoleAuditLogger.log_role_removed_from_user(
                admin_user=admin_user,
                target_user=self.user,
                role_name=role.name,
                team_name=self.team.name
            )

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
