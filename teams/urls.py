from django.urls import path
from .views import TeamDetailView, TeamCreateView, TeamListView, TeamStatusChangeView, TeamStatusHistoryView, TeamCountsView

app_name = 'teams'

urlpatterns = [
    path('', TeamListView.as_view(), name='team_list'),
    path('create/', TeamCreateView.as_view(), name='team_create'),
    path('<int:pk>/', TeamDetailView.as_view(), name='team_detail'),
    path('<int:team_id>/status/', TeamStatusChangeView.as_view(), name='team_status_change'),
    path('<int:pk>/history/', TeamStatusHistoryView.as_view(), name='team_status_history'),
    path('api/counts/', TeamCountsView.as_view(), name='team_counts'),
]
