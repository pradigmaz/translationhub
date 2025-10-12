"""
Management command для создания стандартных ролей системы управления ролями.

Эта команда создает стандартные роли (Руководитель, Редактор, Переводчик, Клинер, Тайпер)
с предустановленными разрешениями, используя DefaultRoleManager.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from teams.role_manager import DefaultRoleManager


class Command(BaseCommand):
    help = "Создает стандартные роли системы с предустановленными разрешениями"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет сделано без фактического выполнения изменений",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод процесса создания ролей",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Принудительно обновить разрешения существующих ролей",
        )
        parser.add_argument(
            "--role",
            type=str,
            help="Создать только указанную роль (по названию)",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""

        # Настройка логирования
        logger = logging.getLogger(__name__)

        dry_run = options["dry_run"]
        verbose = options["verbose"]
        force_update = options["force_update"]
        specific_role = options["role"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("РЕЖИМ ТЕСТИРОВАНИЯ: изменения не будут сохранены")
            )

        try:
            # Получаем список ролей для создания
            if specific_role:
                if not DefaultRoleManager.is_default_role(specific_role):
                    raise CommandError(
                        f'Роль "{specific_role}" не является стандартной'
                    )
                roles_to_process = {
                    specific_role: DefaultRoleManager.DEFAULT_ROLES[specific_role]
                }
                self.stdout.write(f"Обработка роли: {specific_role}")
            else:
                roles_to_process = DefaultRoleManager.DEFAULT_ROLES
                self.stdout.write(
                    f"Обработка всех стандартных ролей: {len(roles_to_process)}"
                )

            if verbose:
                self.stdout.write("Роли для обработки:")
                for role_name in roles_to_process.keys():
                    self.stdout.write(f"  - {role_name}")

            # Счетчики для статистики
            created_count = 0
            updated_count = 0
            skipped_count = 0
            error_count = 0

            # Обрабатываем каждую роль
            for role_name, role_data in roles_to_process.items():
                try:
                    if dry_run:
                        # В режиме dry-run проверяем что будет сделано
                        from teams.models import Role

                        existing_role = Role.objects.filter(name=role_name).first()

                        if existing_role:
                            if force_update:
                                self.stdout.write(
                                    f'[DRY RUN] Роль "{role_name}": будут обновлены разрешения'
                                )
                                updated_count += 1
                            else:
                                self.stdout.write(
                                    f'[DRY RUN] Роль "{role_name}": уже существует, пропускается'
                                )
                                skipped_count += 1
                        else:
                            self.stdout.write(
                                f'[DRY RUN] Роль "{role_name}": будет создана'
                            )
                            created_count += 1
                    else:
                        # Фактическое создание/обновление роли
                        with transaction.atomic():
                            from teams.models import Role

                            existing_role = Role.objects.filter(name=role_name).first()

                            if existing_role and not force_update:
                                skipped_count += 1
                                if verbose:
                                    self.stdout.write(
                                        f'  Роль "{role_name}": уже существует, пропускается'
                                    )
                            else:
                                if existing_role and force_update:
                                    # Обновляем существующую роль
                                    existing_role.description = role_data["description"]
                                    existing_role.is_default = True
                                    existing_role.save()

                                    # Обновляем разрешения
                                    existing_role.permissions.clear()
                                    DefaultRoleManager._assign_permissions_to_role(
                                        existing_role, role_data["permissions"]
                                    )

                                    updated_count += 1
                                    message = f'  Роль "{role_name}": обновлена'
                                    self.stdout.write(self.style.SUCCESS(message))

                                    if verbose:
                                        permissions_count = (
                                            existing_role.get_permission_count()
                                        )
                                        self.stdout.write(
                                            f"    Назначено разрешений: {permissions_count}"
                                        )

                                    logger.info(f"Updated role: {role_name}")
                                else:
                                    # Создаем новую роль
                                    role, created = (
                                        DefaultRoleManager.get_or_create_role(
                                            name=role_name,
                                            description=role_data["description"],
                                            permissions=role_data["permissions"],
                                            user=None  # Системная команда
                                        )
                                    )

                                    if created:
                                        created_count += 1
                                        message = f'  Роль "{role_name}": создана'
                                        self.stdout.write(self.style.SUCCESS(message))

                                        if verbose:
                                            permissions_count = (
                                                role.get_permission_count()
                                            )
                                            self.stdout.write(
                                                f"    Назначено разрешений: {permissions_count}"
                                            )

                                        logger.info(f"Created role: {role_name}")
                                    else:
                                        skipped_count += 1
                                        if verbose:
                                            self.stdout.write(
                                                f'  Роль "{role_name}": уже существовала'
                                            )

                except Exception as e:
                    error_count += 1
                    error_message = (
                        f'  ОШИБКА при обработке роли "{role_name}": {str(e)}'
                    )
                    self.stdout.write(self.style.ERROR(error_message))
                    logger.error(
                        f"Error processing role {role_name}: {str(e)}", exc_info=True
                    )

                    if not dry_run:
                        # В случае ошибки продолжаем обработку остальных ролей
                        continue

            # Выводим итоговую статистику
            self.stdout.write("\n" + "=" * 50)
            self.stdout.write("ИТОГИ СОЗДАНИЯ РОЛЕЙ:")
            self.stdout.write(f"Всего ролей обработано: {len(roles_to_process)}")
            self.stdout.write(f"Создано новых ролей: {created_count}")
            self.stdout.write(f"Обновлено ролей: {updated_count}")
            self.stdout.write(f"Пропущено ролей: {skipped_count}")

            if error_count > 0:
                self.stdout.write(self.style.ERROR(f"Ошибок: {error_count}"))
            else:
                self.stdout.write(self.style.SUCCESS("Ошибок: 0"))

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "\nЭто был тестовый запуск. Для применения изменений "
                        "запустите команду без флага --dry-run"
                    )
                )
            else:
                if created_count > 0 or updated_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS("\nСоздание ролей завершено успешно!")
                    )
                else:
                    self.stdout.write(self.style.SUCCESS("\nВсе роли уже существуют!"))

            # Дополнительная информация о созданных ролях
            if not dry_run and verbose and (created_count > 0 or updated_count > 0):
                self.stdout.write("\nИнформация о стандартных ролях:")
                from teams.models import Role

                for role_name in roles_to_process.keys():
                    try:
                        role = Role.objects.get(name=role_name)
                        permissions_count = role.get_permission_count()
                        usage_count = role.get_usage_count()
                        self.stdout.write(
                            f"  {role_name}: {permissions_count} разрешений, "
                            f"используется {usage_count} раз"
                        )
                    except Role.DoesNotExist:
                        pass

            # Логируем итоги
            logger.info(
                f"Default roles creation completed: "
                f"total={len(roles_to_process)}, created={created_count}, "
                f"updated={updated_count}, skipped={skipped_count}, "
                f"errors={error_count}, dry_run={dry_run}"
            )

        except Exception as e:
            error_message = f"Критическая ошибка при выполнении команды: {str(e)}"
            self.stdout.write(self.style.ERROR(error_message))
            logger.error(error_message, exc_info=True)
            raise CommandError(error_message)
