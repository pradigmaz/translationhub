# Generated manually for content app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('teams', '0005_populate_team_lifecycle_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Название проекта')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
                ('content_folder', models.CharField(max_length=100, unique=True, verbose_name='Папка контента')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлен')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='teams.team', verbose_name='Команда')),
            ],
            options={
                'verbose_name': 'Проект',
                'verbose_name_plural': 'Проекты',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='TextContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Заголовок')),
                ('content', models.TextField(verbose_name='Содержимое')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлен')),
                ('is_draft', models.BooleanField(default=True, verbose_name='Черновик')),
                ('draft_content', models.TextField(blank=True, verbose_name='Черновик контента')),
                ('last_autosave', models.DateTimeField(blank=True, null=True, verbose_name='Последнее автосохранение')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Автор')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='content.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Текстовый контент',
                'verbose_name_plural': 'Текстовый контент',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ImageContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название')),
                ('image', models.ImageField(upload_to='project_images/', verbose_name='Изображение')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Загружено')),
                ('file_size', models.IntegerField(verbose_name='Размер файла (байт)')),
                ('width', models.IntegerField(verbose_name='Ширина')),
                ('height', models.IntegerField(verbose_name='Высота')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='content.project', verbose_name='Проект')),
                ('uploader', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Загрузил')),
            ],
            options={
                'verbose_name': 'Изображение',
                'verbose_name_plural': 'Изображения',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]