from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.create_project, name='create_project'),
    path('<int:pk>/', views.project_detail, name='project_detail'),
    path('<int:pk>/edit/', views.edit_project, name='edit_project'),
    path('<int:pk>/delete/', views.delete_project, name='delete_project'),
    path('<int:pk>/download/', views.download_project_data, name='download_project_data'),
]