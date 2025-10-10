from django.views.generic import TemplateView
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
import random


class MainPageView(TemplateView):
    """Представление главной страницы сайта"""
    template_name = 'main.html'


class DocsView(TemplateView):
    """Представление страницы документации"""
    template_name = 'docs.html'


class TestDropdownView(TemplateView):
    """Тестовое представление для проверки dropdown"""
    template_name = 'test_dropdown.html'


class TestDjangoView(TemplateView):
    """Тестовое представление для проверки Django template engine"""
    template_name = 'test_django.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_time'] = timezone.now()
        context['random_number'] = random.randint(1, 1000)
        
        # Добавляем тестовую команду если есть
        from teams.models import Team
        test_team = Team.objects.first()
        context['test_team'] = test_team
        
        return context