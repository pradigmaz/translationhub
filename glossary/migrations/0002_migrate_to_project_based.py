# Generated manually - migrate glossary from team-based to project-based

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('glossary', '0001_initial'),
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Удаляем старую таблицу (так как данных пока нет)
        migrations.DeleteModel(
            name='GlossaryTerm',
        ),
        
        # Создаем новую таблицу с привязкой к проекту
        migrations.CreateModel(
            name='GlossaryTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('term', models.CharField(max_length=200, verbose_name='Термин')),
                ('definition', models.TextField(verbose_name='Определение')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Создал')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='glossary_terms', to='projects.project', verbose_name='Проект')),
            ],
            options={
                'verbose_name': 'Термин глоссария',
                'verbose_name_plural': 'Термины глоссария',
                'ordering': ['term'],
            },
        ),
        migrations.AddConstraint(
            model_name='glossaryterm',
            constraint=models.UniqueConstraint(fields=('term', 'project'), name='unique_term_per_project'),
        ),
    ]