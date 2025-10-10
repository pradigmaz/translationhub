# users/forms.py

from django import forms
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.exceptions import ValidationError
from PIL import Image
from .models import User


class ProfileForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя.
    Включает поля display_name, email, avatar с валидацией.
    """
    
    class Meta:
        model = User
        fields = ['display_name', 'email', 'avatar']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите отображаемое имя'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите email адрес'
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png'
            })
        }
        labels = {
            'display_name': 'Отображаемое имя',
            'email': 'Email адрес',
            'avatar': 'Аватарка'
        }
        help_texts = {
            'avatar': 'Поддерживаются форматы JPG и PNG, максимальный размер 2MB'
        }

    def clean_avatar(self):
        """
        Валидация аватарки: проверка размера и формата файла.
        """
        avatar = self.cleaned_data.get('avatar')
        
        if avatar:
            # Проверка размера файла (максимум 2MB)
            if avatar.size > 2 * 1024 * 1024:  # 2MB в байтах
                raise ValidationError('Размер файла не должен превышать 2MB')
            
            # Проверка формата файла
            if not avatar.content_type in ['image/jpeg', 'image/png']:
                raise ValidationError('Поддерживаются только JPG и PNG файлы')
            
            # Дополнительная проверка через PIL
            try:
                img = Image.open(avatar)
                img.verify()
            except Exception:
                raise ValidationError('Загруженный файл не является корректным изображением')
        
        return avatar

    def clean_display_name(self):
        """
        Валидация отображаемого имени.
        """
        display_name = self.cleaned_data.get('display_name')
        
        if display_name and len(display_name.strip()) == 0:
            raise ValidationError('Имя для отображения не может быть пустым')
        
        return display_name

    def clean_email(self):
        """
        Валидация email адреса.
        """
        email = self.cleaned_data.get('email')
        
        if email:
            # Проверка уникальности email (исключая текущего пользователя)
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError('Пользователь с таким email уже существует')
        
        return email


class SettingsForm(forms.Form):
    """
    Форма для изменения основных настроек аккаунта.
    """
    email = forms.EmailField(
        label='Email адрес',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый email адрес'
        }),
        help_text='Введите новый email адрес для вашего аккаунта'
    )

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user:
            self.fields['email'].initial = user.email

    def clean_email(self):
        """
        Валидация email адреса для настроек.
        """
        email = self.cleaned_data.get('email')
        
        if email and self.user:
            # Проверка уникальности email (исключая текущего пользователя)
            if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
                raise ValidationError('Пользователь с таким email уже существует')
        
        return email


class CustomPasswordChangeForm(DjangoPasswordChangeForm):
    """
    Кастомная форма смены пароля с Bootstrap стилями.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Добавляем Bootstrap классы к полям
        self.fields['old_password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введите текущий пароль'
        })
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Введите новый пароль'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Подтвердите новый пароль'
        })
        
        # Обновляем labels
        self.fields['old_password'].label = 'Текущий пароль'
        self.fields['new_password1'].label = 'Новый пароль'
        self.fields['new_password2'].label = 'Подтверждение пароля'