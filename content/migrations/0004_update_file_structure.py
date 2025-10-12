# Manual migration for file structure management task 4

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import utils.file_system


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0003_auto_20251010_2116'),
        ('projects', '0004_update_translation_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Update ImageContent to use new upload path
        migrations.AlterField(
            model_name='imagecontent',
            name='image',
            field=models.ImageField(upload_to=utils.file_system.project_image_upload_path, verbose_name='Изображение'),
        ),
        
        # Create ProjectDocument model
        migrations.CreateModel(
            name='ProjectDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='Название')),
                ('document_type', models.CharField(choices=[('glossary', 'Глоссарий'), ('notes', 'Заметки'), ('reference', 'Справочные материалы'), ('other', 'Прочее')], default='other', max_length=20, verbose_name='Тип документа')),
                ('file', models.FileField(upload_to=utils.file_system.project_document_upload_path, verbose_name='Файл')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Загружено')),
                ('file_size', models.IntegerField(verbose_name='Размер файла (байт)')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='projects.project', verbose_name='Проект')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Загрузил')),
            ],
            options={
                'verbose_name': 'Документ проекта',
                'verbose_name_plural': 'Документы проектов',
                'ordering': ['-uploaded_at'],
            },
        ),
        
        # Add indexes for ProjectDocument
        migrations.AddIndex(
            model_name='projectdocument',
            index=models.Index(fields=['project', '-uploaded_at'], name='content_projectdocument_project_uploaded_idx'),
        ),
        migrations.AddIndex(
            model_name='projectdocument',
            index=models.Index(fields=['uploaded_by', '-uploaded_at'], name='content_projectdocument_uploaded_by_uploaded_idx'),
        ),
        migrations.AddIndex(
            model_name='projectdocument',
            index=models.Index(fields=['document_type', '-uploaded_at'], name='content_projectdocument_document_type_uploaded_idx'),
        ),
    ]