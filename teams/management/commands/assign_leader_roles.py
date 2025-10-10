"""
Management command для назначения роли "Руководитель" создателям существующих команд.

Эта команда обновляет существующие команды, создавая TeamMembership записи
для создателей команд и назначая им роль "Руководитель".
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from teams.models import Team, TeamMembership, ensure_leader_role_exists


class Command(BaseCommand):
    help = 'Назначает роль "Руководитель" создателям всех существующих команд'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без фактического выполнения изменений',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод процесса обновления',
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        
        # Настройка логирования
        logger = logging.getLogger(__name__)
        
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('РЕЖИМ ТЕСТИРОВАНИЯ: изменения не будут сохранены')
            )
        
        try:
            # Получаем все команды
            teams = Team.objects.select_related('creator').all()
            total_teams = teams.count()
            
            if total_teams == 0:
                self.stdout.write(
                    self.style.WARNING('В системе нет команд для обновления')
                )
                return
            
            self.stdout.write(f'Найдено команд для обработки: {total_teams}')
            
            # Убеждаемся что роль "Руководитель" существует
            if not dry_run:
                try:
                    leader_role = ensure_leader_role_exists()
                    self.stdout.write(
                        self.style.SUCCESS(f'Роль "Руководитель" готова к использованию')
                    )
                except Exception as e:
                    raise CommandError(f'Ошибка при создании роли "Руководитель": {e}')
            else:
                # В режиме dry-run просто проверяем существование роли
                from teams.models import Role
                try:
                    leader_role = Role.objects.get(name='Руководитель')
                    self.stdout.write('Роль "Руководитель" уже существует')
                except Role.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING('Роль "Руководитель" будет создана')
                    )
                    leader_role = None
            
            # Счетчики для статистики
            updated_count = 0
            already_assigned_count = 0
            error_count = 0
            
            # Обрабатываем каждую команду
            for team in teams:
                try:
                    with transaction.atomic():
                        # Проверяем существует ли уже TeamMembership для создателя
                        existing_membership = TeamMembership.objects.filter(
                            user=team.creator,
                            team=team
                        ).first()
                        
                        if existing_membership:
                            # Проверяем есть ли уже роль "Руководитель"
                            if not dry_run and leader_role:
                                has_leader_role = existing_membership.roles.filter(
                                    name='Руководитель'
                                ).exists()
                                
                                if has_leader_role:
                                    already_assigned_count += 1
                                    if verbose:
                                        self.stdout.write(
                                            f'  Команда "{team.name}": создатель {team.creator.username} '
                                            f'уже имеет роль "Руководитель"'
                                        )
                                else:
                                    # Добавляем роль к существующему membership
                                    if not dry_run:
                                        existing_membership.roles.add(leader_role)
                                    updated_count += 1
                                    
                                    message = (
                                        f'  Команда "{team.name}": добавлена роль "Руководитель" '
                                        f'для создателя {team.creator.username}'
                                    )
                                    if dry_run:
                                        message = f'[DRY RUN] {message}'
                                    
                                    self.stdout.write(self.style.SUCCESS(message))
                                    logger.info(
                                        f'Assigned leader role to existing membership: '
                                        f'user={team.creator.username}, team={team.name}'
                                    )
                            else:
                                # В режиме dry-run или если роль не создана
                                if dry_run:
                                    self.stdout.write(
                                        f'[DRY RUN] Команда "{team.name}": будет добавлена '
                                        f'роль "Руководитель" для создателя {team.creator.username}'
                                    )
                                    updated_count += 1
                        else:
                            # Создаем новый TeamMembership
                            if not dry_run and leader_role:
                                membership = TeamMembership.objects.create(
                                    user=team.creator,
                                    team=team
                                )
                                membership.roles.add(leader_role)
                                updated_count += 1
                                
                                message = (
                                    f'  Команда "{team.name}": создан TeamMembership и назначена '
                                    f'роль "Руководитель" для создателя {team.creator.username}'
                                )
                                self.stdout.write(self.style.SUCCESS(message))
                                logger.info(
                                    f'Created new membership with leader role: '
                                    f'user={team.creator.username}, team={team.name}'
                                )
                            else:
                                # В режиме dry-run
                                if dry_run:
                                    self.stdout.write(
                                        f'[DRY RUN] Команда "{team.name}": будет создан TeamMembership '
                                        f'и назначена роль "Руководитель" для создателя {team.creator.username}'
                                    )
                                    updated_count += 1
                
                except Exception as e:
                    error_count += 1
                    error_message = (
                        f'  ОШИБКА при обработке команды "{team.name}" '
                        f'(создатель: {team.creator.username}): {str(e)}'
                    )
                    self.stdout.write(self.style.ERROR(error_message))
                    logger.error(
                        f'Error processing team {team.name}: {str(e)}',
                        exc_info=True
                    )
                    
                    if not dry_run:
                        # В случае ошибки откатываем транзакцию для этой команды
                        # но продолжаем обработку остальных
                        continue
            
            # Выводим итоговую статистику
            self.stdout.write('\n' + '='*50)
            self.stdout.write('ИТОГИ ОБНОВЛЕНИЯ:')
            self.stdout.write(f'Всего команд обработано: {total_teams}')
            self.stdout.write(f'Обновлено команд: {updated_count}')
            self.stdout.write(f'Уже имели роль: {already_assigned_count}')
            if error_count > 0:
                self.stdout.write(self.style.ERROR(f'Ошибок: {error_count}'))
            else:
                self.stdout.write(self.style.SUCCESS('Ошибок: 0'))
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('\nЭто был тестовый запуск. Для применения изменений '
                                     'запустите команду без флага --dry-run')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('\nОбновление завершено успешно!')
                )
                
            # Логируем итоги
            logger.info(
                f'Leader role assignment completed: '
                f'total={total_teams}, updated={updated_count}, '
                f'already_assigned={already_assigned_count}, errors={error_count}, '
                f'dry_run={dry_run}'
            )
                
        except Exception as e:
            error_message = f'Критическая ошибка при выполнении команды: {str(e)}'
            self.stdout.write(self.style.ERROR(error_message))
            logger.error(error_message, exc_info=True)
            raise CommandError(error_message)