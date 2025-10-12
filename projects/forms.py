# projects/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import Project
from .utils import generate_content_folder


class ProjectForm(forms.ModelForm):
    """Форма для создания/редактирования проектов манги/манхвы"""
    
    class Meta:
        model = Project
        fields = ['title', 'description', 'team', 'project_type', 'age_rating', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название проекта'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание проекта (необязательно)'
            }),
            'team': forms.Select(attrs={
                'class': 'form-select'
            }),
            'project_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'age_rating': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, user=None, selected_team=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.selected_team = selected_team
        
        # Если команда предопределена, скрываем поле выбора команды
        if selected_team:
            self.fields['team'].widget = forms.HiddenInput()
            self.fields['team'].initial = selected_team
        else:
            # Ограничиваем команды только активными командами пользователя
            if user:
                from teams.models import Team
                self.fields['team'].queryset = Team.objects.filter(
                    members=user,
                    status='active'
                ).distinct()
        
        # Делаем поля обязательными
        self.fields['title'].required = True
        self.fields['project_type'].required = True
        self.fields['age_rating'].required = True
        
        # Команда обязательна только если не предопределена
        self.fields['team'].required = not bool(selected_team)
        
        # Добавляем help_text для статуса проекта
        self.fields['status'].help_text = (
            '<strong>Переводим</strong> - активная работа над проектом, '
            '<strong>Переведён</strong> - все главы готовы, '
            '<strong>Заморожен</strong> - временная приостановка, '
            '<strong>Заброшен</strong> - работа прекращена'
        )
    
    def clean_title(self):
        """Валидация названия проекта - минимум 3 символа"""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 3:
            raise ValidationError('Название должно содержать минимум 3 символа')
        return title.strip()
    
    def clean_status(self):
        """Валидация статуса проекта"""
        status = self.cleaned_data.get('status')
        valid_statuses = [choice[0] for choice in Project.STATUS_CHOICES]
        
        if status and status not in valid_statuses:
            raise ValidationError('Выберите корректный статус проекта')
        
        return status
    
    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        
        # Если команда предопределена, используем её
        if self.selected_team:
            cleaned_data['team'] = self.selected_team
        
        return cleaned_data
    
    def save(self, commit=True):
        """Переопределяем метод save для автогенерации content_folder"""
        instance = super().save(commit=False)
        
        # Убеждаемся что команда установлена
        if self.selected_team and not instance.team:
            instance.team = self.selected_team
        
        # Автогенерируем папку если её нет
        if not instance.content_folder and instance.team:
            try:
                instance.content_folder = generate_content_folder(
                    instance.title, 
                    instance.team,  # Передаем команду для изоляции
                    instance.id
                )
            except Exception as e:
                raise ValidationError(f'Ошибка генерации папки: {str(e)}')
        
        if commit:
            instance.save()
        return instance


class ProjectEditForm(forms.ModelForm):
    """Упрощенная форма для редактирования только изменяемых параметров проекта"""
    
    class Meta:
        model = Project
        fields = ['title', 'description', 'status']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название проекта'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание проекта (необязательно)'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Делаем поле title обязательным
        self.fields['title'].required = True
        
        # Добавляем пользовательские подписи для полей
        self.fields['title'].label = 'Название проекта'
        self.fields['description'].label = 'Описание'
        self.fields['status'].label = 'Статус проекта'
        
        # Добавляем help_text для пояснений
        self.fields['title'].help_text = 'Минимум 3 символа'
        self.fields['description'].help_text = 'Необязательное поле'
        self.fields['status'].help_text = (
            '<strong>Переводим</strong> - активная работа над проектом, '
            '<strong>Переведён</strong> - все главы готовы, '
            '<strong>Заморожен</strong> - временная приостановка, '
            '<strong>Заброшен</strong> - работа прекращена'
        )
    
    def clean_title(self):
        """Валидация названия проекта - минимум 3 символа"""
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 3:
            raise ValidationError('Название должно содержать минимум 3 символа')
        return title.strip()
    
    def clean_status(self):
        """Валидация статуса проекта"""
        status = self.cleaned_data.get('status')
        valid_statuses = [choice[0] for choice in Project.STATUS_CHOICES]
        
        if status and status not in valid_statuses:
            raise ValidationError('Выберите корректный статус проекта')
        
        return status
    
    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        
        # Дополнительная проверка на пустое название после обрезки пробелов
        title = cleaned_data.get('title')
        if title and not title.strip():
            raise ValidationError({'title': 'Название не может состоять только из пробелов'})
        
        return cleaned_data