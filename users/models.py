# users/models.py

from django.db import models
# AbstractUser импортируется как основа для создания своей модели пользователя
# со всеми стандартными полями и методами (username, password, email и т.д.).
from django.contrib.auth.models import AbstractUser

# Создается новый класс User, который наследует все от AbstractUser.
# Это стандартная практика для расширения функционала пользователя.
class User(AbstractUser):
    """
    Кастомная модель пользователя.
    """
    # models.CharField - это текстовое поле с ограниченной длиной.
    display_name = models.CharField(
        # Максимальная длина строки в базе данных.
        max_length=100,
        # blank=True означает, что это поле не обязательно для заполнения в формах.
        blank=True,
        # help_text - это текстовая подсказка, которая будет отображаться в админ-панели.
        help_text="Отображаемый никнейм"
    )