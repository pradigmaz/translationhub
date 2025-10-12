"""
Management команда для оптимизации базы данных приложения content
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from content.models import ContentAuditLog, TextContent, Project
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Оптимизирует базу данных приложения content"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cleanup-logs",
            action="store_true",
            help="Очистить старые логи аудита (старше 90 дней)",
        )
        parser.add_argument(
            "--cleanup-drafts",
            action="store_true",
            help="Очистить старые черновики (старше 30 дней без изменений)",
        )
        parser.add_argument(
            "--vacuum",
            action="store_true",
            help="Выполнить VACUUM для SQLite (освободить место)",
        )
        parser.add_argument(
            "--analyze",
            action="store_true",
            help="Обновить статистику таблиц для оптимизатора запросов",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет сделано, но не выполнять изменения",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🔧 Оптимизация базы данных приложения content")
        )

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING("🔍 Режим просмотра (изменения не будут применены)")
            )

        # Очистка логов аудита
        if options["cleanup_logs"]:
            self.cleanup_audit_logs(options["dry_run"])

        # Очистка старых черновиков
        if options["cleanup_drafts"]:
            self.cleanup_old_drafts(options["dry_run"])

        # VACUUM для SQLite
        if options["vacuum"]:
            self.vacuum_database(options["dry_run"])

        # Обновление статистики
        if options["analyze"]:
            self.analyze_database(options["dry_run"])

        self.stdout.write(self.style.SUCCESS("\n✅ Оптимизация завершена"))

    def cleanup_audit_logs(self, dry_run=False):
        """Очищает старые логи аудита"""
        self.stdout.write("\n🗑️  Очистка логов аудита...")

        # Удаляем логи старше 90 дней
        cutoff_date = timezone.now() - timedelta(days=90)
        old_logs = ContentAuditLog.objects.filter(timestamp__lt=cutoff_date)
        count = old_logs.count()

        if count == 0:
            self.stdout.write("  • Старых логов не найдено")
            return

        self.stdout.write(f"  • Найдено {count} старых логов для удаления")

        if not dry_run:
            with transaction.atomic():
                deleted_count, _ = old_logs.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ Удалено {deleted_count} логов")
                )
                logger.info(f"Cleaned up {deleted_count} old audit logs")
        else:
            self.stdout.write("  🔍 (dry-run) Логи будут удалены")

    def cleanup_old_drafts(self, dry_run=False):
        """Очищает старые неиспользуемые черновики"""
        self.stdout.write("\n📝 Очистка старых черновиков...")

        # Находим черновики старше 30 дней без изменений
        cutoff_date = timezone.now() - timedelta(days=30)
        old_drafts = TextContent.objects.filter(
            is_draft=True,
            updated_at__lt=cutoff_date,
            draft_content="",  # Пустые черновики
        )
        count = old_drafts.count()

        if count == 0:
            self.stdout.write("  • Старых черновиков не найдено")
            return

        self.stdout.write(f"  • Найдено {count} старых пустых черновиков")

        if not dry_run:
            with transaction.atomic():
                deleted_count, _ = old_drafts.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ Удалено {deleted_count} черновиков")
                )
                logger.info(f"Cleaned up {deleted_count} old draft texts")
        else:
            self.stdout.write("  🔍 (dry-run) Черновики будут удалены")

    def vacuum_database(self, dry_run=False):
        """Выполняет VACUUM для SQLite"""
        self.stdout.write("\n🗜️  Сжатие базы данных...")

        if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
            self.stdout.write(
                self.style.WARNING("  ⚠️  VACUUM поддерживается только для SQLite")
            )
            return

        if not dry_run:
            try:
                with connection.cursor() as cursor:
                    # Получаем размер БД до VACUUM
                    cursor.execute("PRAGMA page_count")
                    pages_before = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_size")
                    page_size = cursor.fetchone()[0]

                    size_before = pages_before * page_size

                    # Выполняем VACUUM
                    cursor.execute("VACUUM")

                    # Получаем размер после VACUUM
                    cursor.execute("PRAGMA page_count")
                    pages_after = cursor.fetchone()[0]

                    size_after = pages_after * page_size
                    saved_bytes = size_before - size_after

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ VACUUM выполнен. Освобождено: {saved_bytes / 1024:.1f} KB"
                        )
                    )
                    logger.info(f"Database VACUUM completed, saved {saved_bytes} bytes")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Ошибка VACUUM: {e}"))
                logger.error(f"VACUUM failed: {e}")
        else:
            self.stdout.write("  🔍 (dry-run) VACUUM будет выполнен")

    def analyze_database(self, dry_run=False):
        """Обновляет статистику таблиц"""
        self.stdout.write("\n📊 Обновление статистики таблиц...")

        if "sqlite" not in settings.DATABASES["default"]["ENGINE"]:
            self.stdout.write(
                self.style.WARNING("  ⚠️  ANALYZE поддерживается только для SQLite")
            )
            return

        if not dry_run:
            try:
                with connection.cursor() as cursor:
                    # Обновляем статистику для всех таблиц content
                    tables = [
                        "content_project",
                        "content_textcontent",
                        "content_imagecontent",
                        "content_contentauditlog",
                    ]

                    for table in tables:
                        cursor.execute(f"ANALYZE {table}")
                        self.stdout.write(f"  ✅ Статистика обновлена для {table}")

                    logger.info("Database statistics updated for content tables")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ❌ Ошибка ANALYZE: {e}"))
                logger.error(f"ANALYZE failed: {e}")
        else:
            self.stdout.write("  🔍 (dry-run) Статистика будет обновлена")

    def get_database_size(self):
        """Возвращает размер базы данных"""
        if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA page_count")
                    pages = cursor.fetchone()[0]

                    cursor.execute("PRAGMA page_size")
                    page_size = cursor.fetchone()[0]

                    return pages * page_size
            except Exception:
                return 0
        return 0
