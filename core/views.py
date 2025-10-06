from django.views.generic import TemplateView


class MainPageView(TemplateView):
    """Представление главной страницы сайта"""
    template_name = 'main.html'