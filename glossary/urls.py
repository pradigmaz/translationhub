from django.urls import path
from . import views

app_name = 'glossary'

urlpatterns = [
    # URL-маршруты будут добавлены при реализации представлений
    # path('', views.GlossaryListView.as_view(), name='glossary_list'),
    # path('create/', views.GlossaryCreateView.as_view(), name='glossary_create'),
    # path('<int:pk>/', views.GlossaryDetailView.as_view(), name='glossary_detail'),
]