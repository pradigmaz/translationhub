# users/admin.py

# Импортируем сам Django admin, чтобы регистрировать модели.
from django.contrib import admin
# Импортируем UserAdmin - это готовый, мощный интерфейс от Django
# для управления пользователями (с поиском, фильтрами, управлением паролями).
from django.contrib.auth.admin import UserAdmin
# Импортируем нашу кастомную модель User из текущего приложения (users).
from .models import User

# admin.site.register(User, UserAdmin)
# Эта команда "регистрирует" модель User в админ-панели.
# Второй аргумент, UserAdmin, говорит Django: "Используй для этой модели
# свой стандартный, крутой интерфейс для пользователей".
# Без этого в админке не было бы раздела "Users".
admin.site.register(User, UserAdmin)