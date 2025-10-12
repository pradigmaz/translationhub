"""
Команда для назначения дефолтной роли существующим пользователям.

Эта команда полезна для миграции существующих пользователей,
которые были созданы до внедрения системы автоматического
назначения дефолтных ролей.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from teams.models import UserRole
from teams.role_manager import DefaultRoleManager
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    help = 'Назначает дефолтную роль "Пользователь" всем пользователям, у которых нет глобальных ролей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без фактического выполнения',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Назначить дефолтную роль даже пользователям, у которых уже есть роли',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID конкретного пользователя для обработки',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        user_id = options.get('user_id')

        self.stdout.write(
            self.style.SUCCESS('Начинаем назначение дефолтных ролей пользователям...')
        )

        # Получаем дефолтную роль
        default_role = DefaultRoleManager.get_default_user_role()
        if not default_role:
            self.stdout.write(
                self.style.ERROR('Дефолтная роль "Пользователь" не найдена. '
                               'Запустите команду create_default_roles сначала.')
            )
            return

        # Определяем пользователей для обработки
        if user_id:
            try:
                users = User.objects.filter(id=user_id)
                if not users.exists():
                    self.stdout.write(
                        self.style.ERROR(f'Пользователь с ID {user_id} не найден')
                    )
                    return
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Некорректный ID пользователя')
                )
                return
        else:
            users = User.objects.all()

        # Статистика
        total_users = users.count()
        processed_users = 0
        assigned_roles = 0
        skipped_users = 0
        errors = 0

        self.stdout.write(f'Найдено пользователей для обработки: {total_users}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ТЕСТИРОВАНИЯ - изменения не будут сохранены')
            )

        for user in users:
            processed_users += 1
            
            try:
                # Проверяем есть ли у пользователя глобальные роли
                existing_roles = UserRole.objects.filter(user=user, is_active=True)
                
                if existing_roles.exists() and not force:
                    skipped_users += 1
                    self.stdout.write(
                        f'Пропущен пользователь {user.username} (ID: {user.id}) - '
                        f'уже имеет роли: {", ".join(ur.role.name for ur in existing_roles)}'
                    )
                    continue

                # Проверяем есть ли уже дефолтная роль
                has_default_role = existing_roles.filter(role=default_role).exists()
                
                if has_default_role and not force:
                    skipped_users += 1
                    self.stdout.write(
                        f'Пропущен пользователь {user.username} (ID: {user.id}) - '
                        f'уже имеет дефолтную роль'
                    )
                    continue

                if not dry_run:
                    with transaction.atomic():
                        # Назначаем дефолтную роль
                        user_role, created = UserRole.objects.get_or_create(
                            user=user,
                            role=default_role,
                            defaults={
                                'is_active': True,
                                'assigned_by': None  # Автоматическое назначение
                            }
                        )
                        
                        if created or not user_role.is_active:
                            if not created:
                                # Реактивируем роль если она была деактивирована
                                user_role.is_active = True
                                user_role.save()
                            
                            assigned_roles += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Назначена дефолтная роль пользователю '
                                    f'{user.username} (ID: {user.id})'
                                )
                            )
                        else:
                            skipped_users += 1
                            self.stdout.write(
                                f'Пользователь {user.username} (ID: {user.id}) '
                                f'уже имеет активную дефолтную роль'
                            )
                else:
                    # В режиме dry-run просто показываем что будет сделано
                    if not has_default_role:
                        assigned_roles += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Будет назначена дефолтная роль пользователю '
                                f'{user.username} (ID: {user.id})'
                            )
                        )
                    else:
                        skipped_users += 1
                        self.stdout.write(
                            f'[DRY RUN] Пользователь {user.username} (ID: {user.id}) '
                            f'уже имеет дефолтную роль'
                        )

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'Ошибка при обработке пользователя {user.username} (ID: {user.id}): {str(e)}'
                    )
                )
                logger.error(f'Ошибка при назначении дефолтной роли пользователю {user.username}: {str(e)}')

        # Выводим итоговую статистику
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('ИТОГИ НАЗНАЧЕНИЯ ДЕФОЛТНЫХ РОЛЕЙ:'))
        self.stdout.write(f'Всего пользователей обработано: {processed_users}')
        self.stdout.write(f'Назначено дефолтных ролей: {assigned_roles}')
        self.stdout.write(f'Пропущено пользователей: {skipped_users}')
        self.stdout.write(f'Ошибок: {errors}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nЭто был тестовый запуск. Для фактического выполнения '
                                 'запустите команду без флага --dry-run')
            )
        elif assigned_roles > 0:
            self.stdout.write(
                self.style.SUCCESS(f'\nУспешно назначено {assigned_roles} дефолтных ролей!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('\nНикаких изменений не было сделано.')
            )