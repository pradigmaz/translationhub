from django.db import models
from django.conf import settings
from projects.models import Project


class GlossaryTerm(models.Model):
    """Термин в глоссарии проекта"""
    term = models.CharField(max_length=200, verbose_name="Термин")
    definition = models.TextField(verbose_name="Определение")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='glossary_terms', verbose_name="Проект")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Создал")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Термин глоссария"
        verbose_name_plural = "Термины глоссария"
        unique_together = ['term', 'project']
        ordering = ['term']
    
    def __str__(self):
        return f"{self.term} ({self.project.title})"
