# Generated manually for manga project enhancement
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='project_type',
            field=models.CharField(
                choices=[('manga', 'Манга'), ('manhwa', 'Манхва'), ('manhua', 'Маньхуа')],
                default='manga',
                max_length=10,
                verbose_name='Тип проекта'
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='age_rating',
            field=models.CharField(
                choices=[('general', 'Обычная'), ('adult', '18+')],
                default='general',
                max_length=10,
                verbose_name='Возрастной рейтинг'
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='content_folder',
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name='Папка контента'
            ),
        ),
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[
                    ('ongoing', 'Онгоинг'),
                    ('completed', 'Завершен'),
                    ('on_hold', 'Заморожен'),
                    ('dropped', 'Заброшен')
                ],
                default='ongoing',
                max_length=20
            ),
        ),
        migrations.AlterUniqueTogether(
            name='project',
            unique_together={('team', 'content_folder')},
        ),
    ]