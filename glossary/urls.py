from django.urls import path
from . import views

app_name = 'glossary'

urlpatterns = [
    path('project/<int:project_id>/', views.glossary_list, name='glossary_list'),
    path('project/<int:project_id>/create/', views.glossary_create, name='glossary_create'),
    path('project/<int:project_id>/<int:pk>/', views.glossary_detail, name='glossary_detail'),
]