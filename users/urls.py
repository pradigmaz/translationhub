# users/urls.py

# path - функция для определения одного URL-маршрута.
from django.urls import path
# Импортируются готовые View для аутентификации из Django.
# `as auth_views` - это псевдоним для удобства.
from django.contrib.auth import views as auth_views
# Импортируется собственный класс RegisterView из файла views.py.
from .views import RegisterView, DashboardView

# app_name определяет "пространство имен" для этих URL-ов.
# Это позволяет однозначно ссылаться на них, например: {% url 'users:login' %}.
app_name = 'users'

# urlpatterns - это стандартное имя переменной, в которой Django ищет список маршрутов.
# ВАЖНО: это должен быть СПИСОК (в квадратных скобках []), а не словарь.
urlpatterns = [
    # Маршрут для страницы входа.
    # path() принимает URL, View для его обработки, и необязательное имя.
    # auth_views.LoginView.as_view(...) - используется готовый View от Django.
    # В скобках ему передается параметр - какой HTML-шаблон использовать.
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    # Маршрут для выхода из системы. Используется стандартный View без параметров.
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Маршрут для страницы регистрации. Используется собственный RegisterView.
    path('register/', RegisterView.as_view(), name='register'),
    path('dashboard/', DashboardView.as_view(), name='dashboard')
]