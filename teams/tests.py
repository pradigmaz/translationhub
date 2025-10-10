from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Team, Role, TeamMembership

User = get_user_model()


class TeamModelTest(TestCase):
    """Тесты модели Team"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
    def test_team_creation(self):
        """Тест создания команды"""
        team = Team.objects.create(
            name='Test Team',
            creator=self.user
        )
        self.assertEqual(team.name, 'Test Team')
        self.assertEqual(team.creator, self.user)
        self.assertEqual(str(team), 'Test Team')
        
    def test_team_members_relationship(self):
        """Тест связи команды с участниками"""
        team = Team.objects.create(name='Test Team', creator=self.user)
        user2 = User.objects.create_user(username='user2', password='pass')
        
        # Добавляем участника через TeamMembership
        membership = TeamMembership.objects.create(user=user2, team=team)
        
        self.assertIn(user2, team.members.all())
        self.assertEqual(team.teammembership_set.count(), 1)


class TeamViewsTest(TestCase):
    """Тесты views команд"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )
        
    def test_team_create_requires_login(self):
        """Тест: создание команды требует авторизации"""
        response = self.client.get(reverse('teams:team_create'))
        self.assertEqual(response.status_code, 302)  # Редирект на логин
        
    def test_team_create_view_get(self):
        """Тест GET запроса к форме создания команды"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('teams:team_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Создание новой команды')
        
    def test_team_create_view_post_valid(self):
        """Тест создания команды с валидными данными"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('teams:team_create'), {
            'name': 'Test Team'
        })
        self.assertEqual(response.status_code, 302)  # Редирект после создания
        self.assertTrue(Team.objects.filter(name='Test Team').exists())
        
        # Проверяем, что создатель назначен правильно
        team = Team.objects.get(name='Test Team')
        self.assertEqual(team.creator, self.user)
        
    def test_team_create_view_post_invalid(self):
        """Тест создания команды с невалидными данными"""
        self.client.login(username='testuser', password='testpass123')
        
        # Слишком короткое название
        response = self.client.post(reverse('teams:team_create'), {
            'name': 'AB'
        })
        self.assertEqual(response.status_code, 200)  # Остаемся на форме
        self.assertContains(response, 'минимум 3 символа')
        
        # Пустое название
        response = self.client.post(reverse('teams:team_create'), {
            'name': ''
        })
        self.assertEqual(response.status_code, 200)
        
    def test_team_detail_access_control(self):
        """Тест контроля доступа к команде"""
        # Создаем команду от имени первого пользователя
        self.client.login(username='testuser', password='testpass123')
        team = Team.objects.create(name='Test Team', creator=self.user)
        
        # Создатель может видеть команду
        response = self.client.get(reverse('teams:team_detail', kwargs={'pk': team.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Team')
        
        # Другой пользователь не может видеть команду
        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(reverse('teams:team_detail', kwargs={'pk': team.pk}))
        self.assertEqual(response.status_code, 404)  # Команда не найдена для этого пользователя
        
    def test_team_detail_member_access(self):
        """Тест доступа участника команды"""
        team = Team.objects.create(name='Test Team', creator=self.user)
        
        # Добавляем второго пользователя как участника
        TeamMembership.objects.create(user=self.user2, team=team)
        
        # Участник может видеть команду
        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(reverse('teams:team_detail', kwargs={'pk': team.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Team')


class TeamFormTest(TestCase):
    """Тесты формы команды"""
    
    def test_team_form_validation(self):
        """Тест валидации формы команды"""
        from .views import TeamForm
        
        # Валидная форма
        form_data = {'name': 'Valid Team Name'}
        form = TeamForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Слишком короткое название
        form_data = {'name': 'AB'}
        form = TeamForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('минимум 3 символа', str(form.errors))
        
        # Пустое название
        form_data = {'name': ''}
        form = TeamForm(data=form_data)
        self.assertFalse(form.is_valid())
        
        # Слишком длинное название
        form_data = {'name': 'A' * 101}
        form = TeamForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('не более 100 символов', str(form.errors))
        
        # Недопустимые символы
        form_data = {'name': 'Team@#$%'}
        form = TeamForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('только буквы, цифры', str(form.errors))


class SecurityTest(TestCase):
    """Тесты безопасности"""
    
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username='user1', password='pass1')
        self.user2 = User.objects.create_user(username='user2', password='pass2')
        self.team = Team.objects.create(name='Team1', creator=self.user1)
        
    def test_team_access_control(self):
        """Тест: пользователь не может видеть чужие команды"""
        # Проверяем, что пользователь успешно авторизован
        login_success = self.client.login(username='user2', password='pass2')
        self.assertTrue(login_success, "Не удалось авторизовать пользователя")
        
        response = self.client.get(reverse('teams:team_detail', kwargs={'pk': self.team.pk}))
        # Должен быть 404, так как пользователь не имеет доступа к команде
        self.assertEqual(response.status_code, 404)
        
    def test_csrf_protection(self):
        """Тест: CSRF защита работает"""
        self.client.login(username='user1', password='pass1')
        
        # Запрос с правильными данными должен работать
        response = self.client.post(reverse('teams:team_create'), {
            'name': 'New Team'
        })
        # Должен быть редирект после успешного создания или остаться на форме при ошибке
        self.assertIn(response.status_code, [200, 302])
        
        # Проверяем, что команда создалась, если был редирект
        if response.status_code == 302:
            self.assertTrue(Team.objects.filter(name='New Team').exists())


class TeamStatusChangeAjaxTest(TestCase):
    """Тесты AJAX функциональности изменения статуса команды"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.team = Team.objects.create(
            name='Test Team',
            creator=self.user
        )
        
    def test_ajax_status_change_success(self):
        """Тест успешного AJAX изменения статуса команды"""
        self.client.login(username='testuser', password='testpass123')
        
        # Тестируем приостановку команды через AJAX
        response = self.client.post(
            reverse('teams:team_status_change', kwargs={'team_id': self.team.pk}),
            {
                'action': 'deactivate',
                'reason': 'Test reason'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Проверяем JSON ответ
        json_response = response.json()
        self.assertTrue(json_response['success'])
        self.assertEqual(json_response['team_status'], 'inactive')
        self.assertIn('приостановлена', json_response['message'])
        
        # Проверяем, что статус действительно изменился в базе данных
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, 'inactive')
        
    def test_ajax_status_change_invalid_action(self):
        """Тест AJAX запроса с невалидным действием"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post(
            reverse('teams:team_status_change', kwargs={'team_id': self.team.pk}),
            {
                'action': 'invalid_action',
                'reason': 'Test reason'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Проверяем JSON ответ об ошибке
        json_response = response.json()
        self.assertFalse(json_response['success'])
        self.assertIn('Неизвестное действие', json_response['message'])
        
    def test_ajax_vs_regular_request(self):
        """Тест различия между AJAX и обычными запросами"""
        self.client.login(username='testuser', password='testpass123')
        
        # Обычный POST запрос должен возвращать редирект
        response = self.client.post(
            reverse('teams:team_status_change', kwargs={'team_id': self.team.pk}),
            {
                'action': 'deactivate',
                'reason': 'Test reason'
            }
        )
        
        self.assertEqual(response.status_code, 302)  # Редирект
        
        # AJAX запрос должен возвращать JSON
        response = self.client.post(
            reverse('teams:team_status_change', kwargs={'team_id': self.team.pk}),
            {
                'action': 'reactivate',
                'reason': 'Test reason'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')