"""
Management command to clean up orphaned avatar files.
Usage: python manage.py cleanup_avatars
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from users.models import User


class Command(BaseCommand):
    help = 'Удаляет неиспользуемые файлы аватарок из media/avatars/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать файлы для удаления без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Режим предварительного просмотра (файлы не будут удалены)')
            )
        
        # Получаем все используемые аватарки
        used_avatars = set()
        for user in User.objects.exclude(avatar='').exclude(avatar__isnull=True):
            if user.avatar and user.avatar.name:
                used_avatars.add(user.avatar.name)
        
        self.stdout.write(f'Найдено {len(used_avatars)} используемых аватарок')
        
        # Получаем все файлы в директории avatars
        avatars_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
        
        if not os.path.exists(avatars_dir):
            self.stdout.write(
                self.style.WARNING('Директория avatars не существует')
            )
            return
        
        all_files = []
        for root, dirs, files in os.walk(avatars_dir):
            for file in files:
                if file != '.gitkeep':  # Исключаем .gitkeep файл
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
                    all_files.append(relative_path.replace('\\', '/'))  # Нормализуем путь
        
        self.stdout.write(f'Найдено {len(all_files)} файлов в директории avatars')
        
        # Находим неиспользуемые файлы
        orphaned_files = []
        for file_path in all_files:
            if file_path not in used_avatars:
                orphaned_files.append(file_path)
        
        if not orphaned_files:
            self.stdout.write(
                self.style.SUCCESS('Неиспользуемых файлов аватарок не найдено')
            )
            return
        
        self.stdout.write(f'Найдено {len(orphaned_files)} неиспользуемых файлов:')
        
        deleted_count = 0
        for file_path in orphaned_files:
            self.stdout.write(f'  - {file_path}')
            
            if not dry_run:
                try:
                    if default_storage.exists(file_path):
                        default_storage.delete(file_path)
                        deleted_count += 1
                        self.stdout.write(f'    ✓ Удален')
                    else:
                        self.stdout.write(f'    ⚠ Файл не найден')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Ошибка удаления: {e}')
                    )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'Предварительный просмотр завершен. '
                    f'Будет удалено {len(orphaned_files)} файлов.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Очистка завершена. Удалено {deleted_count} файлов.'
                )
            )