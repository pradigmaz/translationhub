# Generated manually for project translation status update
from django.db import migrations, models


def update_existing_statuses(apps, schema_editor):
    """
    Обновляет существующие статусы на новые значения.
    Безопасно мигрирует данные из старой системы статусов в новую.
    """
    Project = apps.get_model('projects', 'Project')
    
    # Маппинг старых статусов на новые
    status_mapping = {
        'ongoing': 'translating',      # Онгоинг -> Переводим
        'completed': 'completed',      # Завершен -> Переведён (остается без изменений)
        'on_hold': 'frozen',          # Заморожен -> Заморожен (новое значение)
        'dropped': 'dropped',         # Заброшен -> Заброшен (остается без изменений)
    }
    
    # Обновляем статусы проектов согласно маппингу
    for old_status, new_status in status_mapping.items():
        updated_count = Project.objects.filter(status=old_status).update(status=new_status)
        if updated_count > 0:
            print(f"Обновлено {updated_count} проектов со статуса '{old_status}' на '{new_status}'")


def reverse_existing_statuses(apps, schema_editor):
    """
    Обратная миграция для отката изменений.
    Возвращает статусы к предыдущим значениям.
    """
    Project = apps.get_model('projects', 'Project')
    
    # Обратный маппинг для отката
    reverse_status_mapping = {
        'translating': 'ongoing',      # Переводим -> Онгоинг
        'completed': 'completed',      # Переведён -> Завершен (остается без изменений)
        'frozen': 'on_hold',          # Заморожен -> Заморожен (старое значение)
        'dropped': 'dropped',         # Заброшен -> Заброшен (остается без изменений)
    }
    
    # Откатываем статусы проектов
    for new_status, old_status in reverse_status_mapping.items():
        updated_count = Project.objects.filter(status=new_status).update(status=old_status)
        if updated_count > 0:
            print(f"Откат: обновлено {updated_count} проектов со статуса '{new_status}' на '{old_status}'")


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_add_project_metadata'),
    ]

    operations = [
        # Сначала обновляем данные с использованием старых choices
        migrations.RunPython(
            update_existing_statuses,
            reverse_existing_statuses,
            hints={'target_db': 'default'}
        ),
        
        # Затем обновляем определение поля с новыми choices
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[
                    ('translating', 'Переводим'),      # Активная работа над проектом
                    ('dropped', 'Заброшен'),           # Команда прекратила работу
                    ('completed', 'Переведён'),        # Все главы готовы
                    ('frozen', 'Заморожен'),           # Временная приостановка
                ],
                default='translating',  # Новый проект по умолчанию "переводим"
                max_length=20,
                verbose_name='Статус проекта'
            ),
        ),
    ]