from django.conf import settings
from django.db import models
# Create your models here.

class Role(models.Model):
    """Модель для хранения возможных ролей (Переводчик, Клинер и т.д.)."""
    name = models.CharField(max_length=50, unique=True, help_text="Изменение роли")
    description = models.TextField(blank=True, help_text="Описание роли")
    
    def __str__(self):
        return self.name
    
class Team(models.Model):
    """Модель команды переводчиков"""
    name = models.CharField(max_length=100)
    creator=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_teams'
    )
    members=models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TeamMembership",
        related_name='teams'
    )
    
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
    
    class Meta:
        unique_together = ('user', 'team')
        
    def __str__(self):
        role_names = ", ".join([role.name for role in self.roles.all()])
        return f"{self.user.username} в команде {self.team.name} как {role_names}"