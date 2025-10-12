from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    # Главная страница редактора
    path('', views.ContentEditorView.as_view(), name='editor'),
    
    # Текстовый редактор
    path('text/', views.TextEditorView.as_view(), name='text_editor'),
    path('text/<int:text_id>/', views.TextEditorView.as_view(), name='text_editor'),
    
    # API для автосохранения
    path('autosave/', views.AutosaveView.as_view(), name='autosave'),
    
    # Управление проектами
    path('project/create/', views.create_project, name='create_project'),
    path('project/<int:project_id>/texts/', views.project_texts, name='project_texts'),
    
    # Управление изображениями
    path('project/<int:project_id>/images/', views.ImageGalleryView.as_view(), name='image_gallery'),
    path('project/<int:project_id>/images/upload/', views.ImageUploadView.as_view(), name='image_upload'),
    
    # Управление документами
    path('project/<int:project_id>/documents/', views.ProjectDocumentListView.as_view(), name='project_documents'),
    path('project/<int:project_id>/documents/upload/', views.ProjectDocumentUploadView.as_view(), name='document_upload'),
    
    # Обработка ошибок
    path('not-found/', views.content_not_found, name='content_not_found'),
]