"""
Простые тесты для проверки утилитных функций управления командами
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Team, TeamMembership, TeamStatusHistory, TeamStatus, TeamStatusChangeType, Role
from .utils import deactivate_team, reactivate_team, disband_team, get_team_status_statistics, can_perform_team_action

User = get_user_model()


class TeamUtilsTestCase(TestCase):
    """Тесты для утилитных функций управления командами"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.user1 = User.objects.create_user(username='leader', email='leader@test.com')
        self.user2 = User.objects.create_user(username='member', email='member@test.com')
        self.user3 = User.objects.create_user(username='outsider', email='outsider@test.com')
        
        self.team = Team.objects.create(
            name='Test Team',
            creator=self.user1,
            status=TeamStatus.ACTIVE
        )
        
        # Создаем участника команды
        TeamMembership.objects.create(
            user=self.user2,
            team=self.team,
            is_active=True
        )
    
    def test_deactivate_team_success(self):
        """Тест успешной приостановки команды"""
        result = deactivate_team(self.team, self.user1, "Test deactivation")
        
        self.assertTrue(result)
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, TeamStatus.INACTIVE)
        
        # Проверяем запись в истории
        history = TeamStatusHistory.objects.filter(team=self.team).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.change_type, TeamStatusChangeType.DEACTIVATED)
        self.assertEqual(history.changed_by, self.user1)
        self.assertEqual(history.reason, "Test deactivation")
    
    def test_deactivate_team_permission_error(self):
        """Тест ошибки прав при приостановке команды"""
        with self.assertRaises(PermissionError):
            deactivate_team(self.team, self.user3, "Unauthorized attempt")
    
    def test_deactivate_team_invalid_status(self):
        """Тест ошибки при попытке приостановить неактивную команду"""
        self.team.status = TeamStatus.INACTIVE
        self.team.save()
        
        with self.assertRaises(ValueError):
            deactivate_team(self.team, self.user1, "Invalid status")
    
    def test_reactivate_team_success(self):
        """Тест успешного возобновления команды"""
        # Сначала приостанавливаем команду
        self.team.status = TeamStatus.INACTIVE
        self.team.save()
        
        result = reactivate_team(self.team, self.user1, "Test reactivation")
        
        self.assertTrue(result)
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, TeamStatus.ACTIVE)
        
        # Проверяем, что участники реактивированы
        membership = TeamMembership.objects.get(team=self.team, user=self.user2)
        self.assertTrue(membership.is_active)
    
    def test_disband_team_success(self):
        """Тест успешного роспуска команды"""
        result = disband_team(self.team, self.user1, "Test disbanding")
        
        self.assertTrue(result)
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, TeamStatus.DISBANDED)
        
        # Проверяем, что участники деактивированы
        membership = TeamMembership.objects.get(team=self.team, user=self.user2)
        self.assertFalse(membership.is_active)
    
    def test_get_team_status_statistics(self):
        """Тест получения статистики команд"""
        # Создаем дополнительные команды
        Team.objects.create(name='Inactive Team', creator=self.user1, status=TeamStatus.INACTIVE)
        Team.objects.create(name='Disbanded Team', creator=self.user1, status=TeamStatus.DISBANDED)
        
        stats = get_team_status_statistics(self.user1)
        
        self.assertEqual(stats['active'], 1)
        self.assertEqual(stats['inactive'], 1)
        self.assertEqual(stats['disbanded'], 1)
        self.assertEqual(stats['total'], 3)
    
    def test_can_perform_team_action(self):
        """Тест проверки возможности выполнения действий"""
        # Тест для активной команды
        can_deactivate, reason = can_perform_team_action(self.team, self.user1, 'deactivate')
        self.assertTrue(can_deactivate)
        self.assertEqual(reason, "")
        
        # Тест для пользователя без прав
        can_deactivate, reason = can_perform_team_action(self.team, self.user3, 'deactivate')
        self.assertFalse(can_deactivate)
        self.assertEqual(reason, "Недостаточно прав для управления командой")
        
        # Тест для неактивной команды
        self.team.status = TeamStatus.INACTIVE
        self.team.save()
        
        can_reactivate, reason = can_perform_team_action(self.team, self.user1, 'reactivate')
        self.assertTrue(can_reactivate)
        
        can_deactivate, reason = can_perform_team_action(self.team, self.user1, 'deactivate')
        self.assertFalse(can_deactivate)
        self.assertEqual(reason, "Можно приостановить только активную команду")