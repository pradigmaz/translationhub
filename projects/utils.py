# projects/utils.py

import re
from django.utils.text import slugify


def generate_content_folder(title, team, project_id=None):
    """
    Генерирует уникальное имя папки из названия проекта в рамках команды
    
    Args:
        title: Название проекта
        team: Команда, к которой принадлежит проект
        project_id: ID проекта (для исключения при обновлении)
    
    Returns:
        str: Уникальное имя папки в рамках команды
    """
    # Базовое имя из заголовка
    base_name = slugify(title, allow_unicode=False)
    
    # Если пустое, используем fallback
    if not base_name:
        base_name = 'project'
    
    # Ограничиваем длину
    base_name = base_name[:50]
    
    # Проверяем уникальность ТОЛЬКО в рамках команды
    folder_name = base_name
    counter = 1
    
    while True:
        # Исключаем текущий проект при обновлении
        from .models import Project
        queryset = Project.objects.filter(
            content_folder=folder_name,
            team=team  # Уникальность только в рамках команды
        )
        if project_id:
            queryset = queryset.exclude(id=project_id)
            
        if not queryset.exists():
            break
            
        folder_name = f"{base_name}_{counter}"
        counter += 1
    
    return folder_name


def validate_folder_name(folder_name):
    """
    Валидирует имя папки
    
    Args:
        folder_name: Имя папки для валидации
        
    Returns:
        bool: True если валидно
        
    Raises:
        ValueError: Если имя папки содержит недопустимые символы
    """
    if not folder_name:
        raise ValueError('Имя папки не может быть пустым')
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', folder_name):
        raise ValueError('Папка может содержать только буквы, цифры, дефисы и подчеркивания')
    
    if len(folder_name) > 100:
        raise ValueError('Имя папки не может быть длиннее 100 символов')
        
    return True