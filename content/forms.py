from django import forms
from django.core.exceptions import ValidationError
from tinymce.widgets import TinyMCE
from projects.models import Project
from .models import TextContent, ImageContent, ProjectDocument


class TextContentForm(forms.ModelForm):
    """Форма для редактирования текстового контента с TinyMCE"""
    
    class Meta:
        model = TextContent
        fields = ['title', 'content', 'project', 'is_draft']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите заголовок текста'
            }),
            'content': TinyMCE(attrs={'cols': 80, 'rows': 30}),
            'project': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_draft': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ограничиваем проекты только теми, к которым у пользователя есть доступ
        if user:
            self.fields['project'].queryset = Project.objects.filter(
                team__members=user,
                team__teammembership__is_active=True,
                team__status='active'
            ).distinct()
        
        # Делаем поля обязательными
        self.fields['title'].required = True
        self.fields['project'].required = True
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title or len(title.strip()) < 3:
            raise ValidationError('Заголовок должен содержать минимум 3 символа')
        return title.strip()


class ImageUploadForm(forms.ModelForm):
    """Форма для загрузки изображений"""
    
    class Meta:
        model = ImageContent
        fields = ['title', 'image', 'project']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название изображения'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/webp'
            }),
            'project': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ограничиваем проекты только теми, к которым у пользователя есть доступ
        if user:
            self.fields['project'].queryset = Project.objects.filter(
                team__members=user,
                team__teammembership__is_active=True,
                team__status='active'
            ).distinct()
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        
        if image:
            # Проверяем размер файла (максимум 10MB)
            if image.size > 10 * 1024 * 1024:
                raise ValidationError('Размер файла не должен превышать 10MB')
            
            # Проверяем тип файла
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if image.content_type not in allowed_types:
                raise ValidationError('Поддерживаются только файлы JPG, PNG и WEBP')
        
        return image


class ProjectDocumentForm(forms.ModelForm):
    """Форма для загрузки документов проекта"""
    
    class Meta:
        model = ProjectDocument
        fields = ['title', 'document_type', 'file', 'project']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название документа'
            }),
            'document_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.txt,.doc,.docx,.csv,.json,.md'
            }),
            'project': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ограничиваем проекты только теми, к которым у пользователя есть доступ
        if user:
            self.fields['project'].queryset = Project.objects.filter(
                team__members=user,
                team__teammembership__is_active=True,
                team__status='active'
            ).distinct()
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if file:
            # Проверяем размер файла (максимум 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('Размер файла не должен превышать 10MB')
            
            # Проверяем тип файла
            allowed_types = [
                'application/pdf', 'text/plain', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/csv', 'application/json', 'text/markdown'
            ]
            if hasattr(file, 'content_type') and file.content_type not in allowed_types:
                raise ValidationError('Поддерживаются только файлы: PDF, TXT, DOC, DOCX, CSV, JSON, MD')
        
        return file