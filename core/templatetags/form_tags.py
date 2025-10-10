from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def add_class(field, css_class):
    """Добавляет CSS класс к полю формы Django"""
    return field.as_widget(attrs={'class': css_class})

@register.filter
def avatar_url(user):
    """Возвращает URL аватарки пользователя или None если аватарки нет"""
    if user and hasattr(user, 'avatar') and user.avatar:
        return user.avatar.url
    return None

@register.inclusion_tag('users/components/avatar.html')
def user_avatar(user, size='40', css_class=''):
    """
    Отображает аватарку пользователя или Font Awesome заглушку.
    
    Args:
        user: объект пользователя
        size: размер аватарки в пикселях (по умолчанию 40)
        css_class: дополнительные CSS классы
    """
    return {
        'user': user,
        'avatar_url': avatar_url(user),
        'size': size,
        'css_class': css_class
    }