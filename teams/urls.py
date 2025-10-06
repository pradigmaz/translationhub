from django.urls import path
from .views import TeamDetailView, TeamCreateView

app_name = 'teams'

urlpatterns = [
    path('create/', TeamCreateView.as_view(), name='team_create'),
    path('<int:pk>/', TeamDetailView.as_view(), name='team_detail')
]
