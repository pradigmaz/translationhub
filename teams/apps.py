from django.apps import AppConfig


class TeamsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'teams'
    
    def ready(self):
        """
        Инициализация приложения teams.
        
        Подключает сигналы для автоматического управления ролями
        и добавляет методы работы с ролями к модели User.
        """
        import teams.signals  # noqa
        from teams.user_mixins import add_role_methods_to_user
        add_role_methods_to_user()
