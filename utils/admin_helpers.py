"""
Вспомогательные методы для административного интерфейса файловой системы.
"""

from django.utils import timezone
from django.conf import settings
from django.db.models import Count, Sum
from pathlib import Path
import os
import hashlib

from utils.file_system import FilePathManager, DirectoryManager, FileCleanupManager
from users.models import User
from teams.models import Team
from projects.models import Project
from content.models import ImageContent, ProjectDocument


class FileSystemAdminHelpers:
    """Вспомогательные методы для админки файловой системы"""
    
    @staticmethod
    def build_file_tree(root_path=''):
        """Построить дерево файлов"""
        media_root = Path(settings.MEDIA_ROOT)
        if root_path:
            current_path = media_root / root_path
        else:
            current_path = media_root
        
        def build_node(path):
            """Построить узел дерева"""
            node = {
                'name': path.name or 'media',
                'path': str(path.relative_to(media_root)) if path != media_root else '',
                'is_dir': path.is_dir(),
                'size': 0,
                'children': []
            }
            
            if path.is_file():
                try:
                    node['size'] = path.stat().st_size
                    node['modified'] = timezone.datetime.fromtimestamp(path.stat().st_mtime)
                except:
                    pass
            elif path.is_dir():
                try:
                    children = []
                    total_size = 0
                    
                    for child in sorted(path.iterdir()):
                        if child.name.startswith('.'):
                            continue
                        
                        child_node = build_node(child)
                        children.append(child_node)
                        total_size += child_node['size']
                    
                    node['children'] = children
                    node['size'] = total_size
                    node['file_count'] = len([c for c in children if not c['is_dir']])
                    node['dir_count'] = len([c for c in children if c['is_dir']])
                    
                except PermissionError:
                    node['error'] = 'Permission denied'
                except Exception as e:
                    node['error'] = str(e)
            
            return node
        
        try:
            return build_node(current_path)
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def get_structure_statistics():
        """Получить статистику структуры"""
        stats = {
            'total_users': User.objects.count(),
            'total_teams': Team.objects.count(),
            'total_projects': Project.objects.count(),
            'users_with_files': 0,
            'teams_with_files': 0,
            'projects_with_files': 0,
            'missing_user_dirs': [],
            'missing_team_dirs': [],
            'missing_project_dirs': []
        }
        
        media_root = Path(settings.MEDIA_ROOT)
        
        # Проверяем пользователей
        for user in User.objects.all():
            user_path = FilePathManager.get_user_path(user.id)
            if user_path.exists():
                stats['users_with_files'] += 1
            else:
                stats['missing_user_dirs'].append({
                    'id': user.id,
                    'username': user.username,
                    'path': str(user_path.relative_to(media_root))
                })
        
        # Проверяем команды
        for team in Team.objects.all():
            team_path = FilePathManager.get_team_path(team.id)
            if team_path.exists():
                stats['teams_with_files'] += 1
            else:
                stats['missing_team_dirs'].append({
                    'id': team.id,
                    'name': team.name,
                    'path': str(team_path.relative_to(media_root))
                })
        
        # Проверяем проекты
        for project in Project.objects.all():
            project_path = FilePathManager.get_project_path(project.team.id, project.content_folder)
            if project_path.exists():
                stats['projects_with_files'] += 1
            else:
                stats['missing_project_dirs'].append({
                    'id': project.id,
                    'title': project.title,
                    'team': project.team.name,
                    'path': str(project_path.relative_to(media_root))
                })
        
        return stats
    
    @staticmethod
    def get_general_file_statistics():
        """Получить общую статистику файлов"""
        stats = {
            'total_images': ImageContent.objects.count(),
            'total_documents': ProjectDocument.objects.count(),
            'total_file_size': 0,
            'avg_file_size': 0,
            'file_types': {},
            'upload_trends': []
        }
        
        # Статистика изображений
        image_stats = ImageContent.objects.aggregate(
            total_size=Sum('file_size'),
            count=Count('id')
        )
        
        if image_stats['total_size']:
            stats['total_file_size'] += image_stats['total_size']
        
        if image_stats['count'] > 0:
            stats['avg_file_size'] = image_stats['total_size'] / image_stats['count']
        
        # Статистика по типам файлов
        doc_types = ProjectDocument.objects.values('document_type').annotate(
            count=Count('id'),
            total_size=Sum('file_size')
        )
        
        for doc_type in doc_types:
            stats['file_types'][doc_type['document_type']] = {
                'count': doc_type['count'],
                'size': doc_type['total_size'] or 0
            }
        
        # Тренды загрузок (последние 30 дней)
        from datetime import timedelta
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        daily_uploads = ImageContent.objects.filter(
            uploaded_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(uploaded_at)'}
        ).values('day').annotate(
            count=Count('id'),
            size=Sum('file_size')
        ).order_by('day')
        
        stats['upload_trends'] = list(daily_uploads)
        
        return stats
    
    @staticmethod
    def get_user_file_statistics():
        """Получить статистику файлов по пользователям"""
        user_stats = []
        
        for user in User.objects.all()[:50]:  # Ограничиваем для производительности
            user_path = FilePathManager.get_user_path(user.id)
            
            stats = {
                'id': user.id,
                'username': user.username,
                'display_name': getattr(user, 'display_name', user.username),
                'has_avatar': bool(user.avatar),
                'directory_exists': user_path.exists(),
                'directory_size': 0,
                'file_count': 0,
                'images_uploaded': ImageContent.objects.filter(uploader=user).count(),
                'documents_uploaded': ProjectDocument.objects.filter(uploaded_by=user).count()
            }
            
            if user_path.exists():
                try:
                    total_size = 0
                    file_count = 0
                    
                    for file_path in user_path.rglob('*'):
                        if file_path.is_file():
                            file_count += 1
                            total_size += file_path.stat().st_size
                    
                    stats['directory_size'] = total_size
                    stats['file_count'] = file_count
                    
                except Exception as e:
                    stats['error'] = str(e)
            
            user_stats.append(stats)
        
        return sorted(user_stats, key=lambda x: x['directory_size'], reverse=True)
    
    @staticmethod
    def get_team_file_statistics():
        """Получить статистику файлов по командам"""
        team_stats = []
        
        for team in Team.objects.all():
            team_path = FilePathManager.get_team_path(team.id)
            
            stats = {
                'id': team.id,
                'name': team.name,
                'status': team.status,
                'directory_exists': team_path.exists(),
                'directory_size': 0,
                'file_count': 0,
                'project_count': team.projects.count(),
                'member_count': team.members.count()
            }
            
            if team_path.exists():
                try:
                    total_size = 0
                    file_count = 0
                    
                    for file_path in team_path.rglob('*'):
                        if file_path.is_file():
                            file_count += 1
                            total_size += file_path.stat().st_size
                    
                    stats['directory_size'] = total_size
                    stats['file_count'] = file_count
                    
                except Exception as e:
                    stats['error'] = str(e)
            
            team_stats.append(stats)
        
        return sorted(team_stats, key=lambda x: x['directory_size'], reverse=True)
    
    @staticmethod
    def get_project_file_statistics():
        """Получить статистику файлов по проектам"""
        project_stats = []
        
        for project in Project.objects.select_related('team')[:100]:  # Ограничиваем для производительности
            project_path = FilePathManager.get_project_path(project.team.id, project.content_folder)
            
            stats = {
                'id': project.id,
                'title': project.title,
                'team_name': project.team.name,
                'status': project.status,
                'directory_exists': project_path.exists(),
                'directory_size': 0,
                'file_count': 0,
                'images_count': ImageContent.objects.filter(project=project).count(),
                'documents_count': ProjectDocument.objects.filter(project=project).count()
            }
            
            if project_path.exists():
                try:
                    total_size = 0
                    file_count = 0
                    
                    for file_path in project_path.rglob('*'):
                        if file_path.is_file():
                            file_count += 1
                            total_size += file_path.stat().st_size
                    
                    stats['directory_size'] = total_size
                    stats['file_count'] = file_count
                    
                except Exception as e:
                    stats['error'] = str(e)
            
            project_stats.append(stats)
        
        return sorted(project_stats, key=lambda x: x['directory_size'], reverse=True)
    
    @staticmethod
    def get_large_files(limit=20):
        """Получить список самых больших файлов"""
        large_files = []
        media_root = Path(settings.MEDIA_ROOT)
        
        # Собираем все файлы и их размеры
        all_files = []
        
        try:
            for file_path in media_root.rglob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    try:
                        size = file_path.stat().st_size
                        all_files.append({
                            'path': str(file_path.relative_to(media_root)),
                            'name': file_path.name,
                            'size': size,
                            'modified': timezone.datetime.fromtimestamp(file_path.stat().st_mtime)
                        })
                    except:
                        continue
            
            # Сортируем по размеру и берем топ
            large_files = sorted(all_files, key=lambda x: x['size'], reverse=True)[:limit]
            
        except Exception as e:
            large_files = [{'error': str(e)}]
        
        return large_files
    
    @staticmethod
    def check_structure_integrity():
        """Проверить целостность структуры файлов"""
        report = {
            'missing_directories': [],
            'orphaned_directories': [],
            'permission_issues': [],
            'broken_links': [],
            'summary': {
                'total_issues': 0,
                'critical_issues': 0,
                'warnings': 0
            }
        }
        
        media_root = Path(settings.MEDIA_ROOT)
        
        # Проверяем обязательные директории
        required_dirs = [
            media_root / 'users',
            media_root / 'teams',
            media_root / 'temp'
        ]
        
        for dir_path in required_dirs:
            if not dir_path.exists():
                report['missing_directories'].append({
                    'path': str(dir_path.relative_to(media_root)),
                    'type': 'system',
                    'severity': 'critical'
                })
                report['summary']['critical_issues'] += 1
        
        # Проверяем директории пользователей
        for user in User.objects.all():
            user_path = FilePathManager.get_user_path(user.id)
            if not user_path.exists() and user.avatar:
                report['missing_directories'].append({
                    'path': str(user_path.relative_to(media_root)),
                    'type': 'user',
                    'user_id': user.id,
                    'username': user.username,
                    'severity': 'warning'
                })
                report['summary']['warnings'] += 1
        
        # Проверяем директории команд
        for team in Team.objects.all():
            team_path = FilePathManager.get_team_path(team.id)
            if not team_path.exists():
                report['missing_directories'].append({
                    'path': str(team_path.relative_to(media_root)),
                    'type': 'team',
                    'team_id': team.id,
                    'team_name': team.name,
                    'severity': 'warning'
                })
                report['summary']['warnings'] += 1
        
        # Проверяем директории проектов
        for project in Project.objects.select_related('team'):
            project_path = FilePathManager.get_project_path(project.team.id, project.content_folder)
            if not project_path.exists():
                has_files = (ImageContent.objects.filter(project=project).exists() or 
                           ProjectDocument.objects.filter(project=project).exists())
                
                if has_files:
                    report['missing_directories'].append({
                        'path': str(project_path.relative_to(media_root)),
                        'type': 'project',
                        'project_id': project.id,
                        'project_title': project.title,
                        'team_name': project.team.name,
                        'severity': 'critical'
                    })
                    report['summary']['critical_issues'] += 1
        
        # Ищем осиротевшие директории
        try:
            users_dir = media_root / 'users'
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir() and user_dir.name.isdigit():
                        user_id = int(user_dir.name)
                        if not User.objects.filter(id=user_id).exists():
                            report['orphaned_directories'].append({
                                'path': str(user_dir.relative_to(media_root)),
                                'type': 'user',
                                'user_id': user_id,
                                'severity': 'warning'
                            })
                            report['summary']['warnings'] += 1
            
            teams_dir = media_root / 'teams'
            if teams_dir.exists():
                for team_dir in teams_dir.iterdir():
                    if team_dir.is_dir() and team_dir.name.isdigit():
                        team_id = int(team_dir.name)
                        if not Team.objects.filter(id=team_id).exists():
                            report['orphaned_directories'].append({
                                'path': str(team_dir.relative_to(media_root)),
                                'type': 'team',
                                'team_id': team_id,
                                'severity': 'warning'
                            })
                            report['summary']['warnings'] += 1
        
        except Exception as e:
            report['orphaned_directories'].append({
                'error': str(e),
                'severity': 'error'
            })
        
        report['summary']['total_issues'] = (
            report['summary']['critical_issues'] + 
            report['summary']['warnings']
        )
        
        return report
    
    @staticmethod
    def find_orphaned_files():
        """Найти осиротевшие файлы"""
        orphaned = {
            'user_files': [],
            'team_files': [],
            'project_files': [],
            'unknown_files': [],
            'summary': {
                'total_files': 0,
                'total_size': 0
            }
        }
        
        media_root = Path(settings.MEDIA_ROOT)
        
        try:
            # Проверяем файлы пользователей
            users_dir = media_root / 'users'
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir() and user_dir.name.isdigit():
                        user_id = int(user_dir.name)
                        user_exists = User.objects.filter(id=user_id).exists()
                        
                        for file_path in user_dir.rglob('*'):
                            if file_path.is_file():
                                file_info = {
                                    'path': str(file_path.relative_to(media_root)),
                                    'size': file_path.stat().st_size,
                                    'modified': timezone.datetime.fromtimestamp(file_path.stat().st_mtime),
                                    'user_id': user_id,
                                    'user_exists': user_exists
                                }
                                
                                if not user_exists:
                                    orphaned['user_files'].append(file_info)
                                    orphaned['summary']['total_files'] += 1
                                    orphaned['summary']['total_size'] += file_info['size']
            
            # Проверяем файлы команд
            teams_dir = media_root / 'teams'
            if teams_dir.exists():
                for team_dir in teams_dir.iterdir():
                    if team_dir.is_dir() and team_dir.name.isdigit():
                        team_id = int(team_dir.name)
                        team_exists = Team.objects.filter(id=team_id).exists()
                        
                        for file_path in team_dir.rglob('*'):
                            if file_path.is_file():
                                file_info = {
                                    'path': str(file_path.relative_to(media_root)),
                                    'size': file_path.stat().st_size,
                                    'modified': timezone.datetime.fromtimestamp(file_path.stat().st_mtime),
                                    'team_id': team_id,
                                    'team_exists': team_exists
                                }
                                
                                if not team_exists:
                                    orphaned['team_files'].append(file_info)
                                    orphaned['summary']['total_files'] += 1
                                    orphaned['summary']['total_size'] += file_info['size']
        
        except Exception as e:
            orphaned['error'] = str(e)
        
        return orphaned
    
    @staticmethod
    def check_file_permissions():
        """Проверить права доступа к файлам"""
        issues = {
            'unreadable_files': [],
            'unwritable_directories': [],
            'permission_errors': [],
            'summary': {
                'total_issues': 0
            }
        }
        
        media_root = Path(settings.MEDIA_ROOT)
        
        try:
            for file_path in media_root.rglob('*'):
                try:
                    if file_path.is_file():
                        if not os.access(file_path, os.R_OK):
                            issues['unreadable_files'].append({
                                'path': str(file_path.relative_to(media_root)),
                                'permissions': oct(file_path.stat().st_mode)
                            })
                    elif file_path.is_dir():
                        if not os.access(file_path, os.W_OK):
                            issues['unwritable_directories'].append({
                                'path': str(file_path.relative_to(media_root)),
                                'permissions': oct(file_path.stat().st_mode)
                            })
                except PermissionError as e:
                    issues['permission_errors'].append({
                        'path': str(file_path.relative_to(media_root)),
                        'error': str(e)
                    })
                except Exception:
                    continue
        
        except Exception as e:
            issues['error'] = str(e)
        
        issues['summary']['total_issues'] = (
            len(issues['unreadable_files']) + 
            len(issues['unwritable_directories']) + 
            len(issues['permission_errors'])
        )
        
        return issues
    
    @staticmethod
    def find_duplicate_files():
        """Найти дублирующиеся файлы"""
        duplicates = {
            'duplicate_groups': [],
            'summary': {
                'total_duplicates': 0,
                'wasted_space': 0
            }
        }
        
        media_root = Path(settings.MEDIA_ROOT)
        
        try:
            file_hashes = {}
            
            # Вычисляем хеши файлов
            for file_path in media_root.rglob('*'):
                if file_path.is_file() and file_path.stat().st_size > 1024:  # Только файлы больше 1KB
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        
                        if file_hash not in file_hashes:
                            file_hashes[file_hash] = []
                        
                        file_hashes[file_hash].append({
                            'path': str(file_path.relative_to(media_root)),
                            'size': file_path.stat().st_size,
                            'modified': timezone.datetime.fromtimestamp(file_path.stat().st_mtime)
                        })
                    except Exception:
                        continue
            
            # Находим дубликаты
            for file_hash, files in file_hashes.items():
                if len(files) > 1:
                    duplicates['duplicate_groups'].append({
                        'hash': file_hash,
                        'files': files,
                        'count': len(files),
                        'size': files[0]['size'],
                        'wasted_space': files[0]['size'] * (len(files) - 1)
                    })
                    
                    duplicates['summary']['total_duplicates'] += len(files) - 1
                    duplicates['summary']['wasted_space'] += files[0]['size'] * (len(files) - 1)
        
        except Exception as e:
            duplicates['error'] = str(e)
        
        return duplicates
    
    @staticmethod
    def cleanup_orphaned_files(dry_run=True):
        """Очистить осиротевшие файлы"""
        result = {
            'success': True,
            'dry_run': dry_run,
            'files_deleted': 0,
            'space_freed': 0,
            'errors': []
        }
        
        try:
            orphaned = FileSystemAdminHelpers.find_orphaned_files()
            
            all_orphaned = (
                orphaned['user_files'] + 
                orphaned['team_files'] + 
                orphaned['project_files']
            )
            
            for file_info in all_orphaned:
                try:
                    file_path = Path(settings.MEDIA_ROOT) / file_info['path']
                    
                    if not dry_run:
                        file_path.unlink()
                    
                    result['files_deleted'] += 1
                    result['space_freed'] += file_info['size']
                    
                except Exception as e:
                    result['errors'].append({
                        'file': file_info['path'],
                        'error': str(e)
                    })
        
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def fix_file_permissions():
        """Исправить права доступа к файлам"""
        result = {
            'success': True,
            'files_fixed': 0,
            'directories_fixed': 0,
            'errors': []
        }
        
        try:
            media_root = Path(settings.MEDIA_ROOT)
            
            for file_path in media_root.rglob('*'):
                try:
                    if file_path.is_file():
                        # Устанавливаем права 644 для файлов
                        file_path.chmod(0o644)
                        result['files_fixed'] += 1
                    elif file_path.is_dir():
                        # Устанавливаем права 755 для директорий
                        file_path.chmod(0o755)
                        result['directories_fixed'] += 1
                except Exception as e:
                    result['errors'].append({
                        'path': str(file_path.relative_to(media_root)),
                        'error': str(e)
                    })
        
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def validate_and_fix_structure():
        """Валидировать и исправить структуру"""
        result = {
            'success': True,
            'directories_created': 0,
            'issues_fixed': 0,
            'errors': []
        }
        
        try:
            # Создаем базовые директории
            media_root = Path(settings.MEDIA_ROOT)
            
            base_dirs = ['users', 'teams', 'temp']
            for dir_name in base_dirs:
                dir_path = media_root / dir_name
                if not dir_path.exists():
                    DirectoryManager.ensure_directory_exists(dir_path)
                    result['directories_created'] += 1
            
            # Создаем директории для пользователей с аватарками
            for user in User.objects.filter(avatar__isnull=False):
                user_path = FilePathManager.get_user_path(user.id)
                if not user_path.exists():
                    DirectoryManager.create_user_directory(user.id)
                    result['directories_created'] += 1
            
            # Создаем директории для команд
            for team in Team.objects.all():
                team_path = FilePathManager.get_team_path(team.id)
                if not team_path.exists():
                    DirectoryManager.create_team_directory(team.id)
                    result['directories_created'] += 1
            
            # Создаем директории для проектов с файлами
            for project in Project.objects.select_related('team'):
                has_files = (ImageContent.objects.filter(project=project).exists() or 
                           ProjectDocument.objects.filter(project=project).exists())
                
                if has_files:
                    project_path = FilePathManager.get_project_path(project.team.id, project.content_folder)
                    if not project_path.exists():
                        DirectoryManager.create_project_directory(project.team.id, project.content_folder)
                        result['directories_created'] += 1
        
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def create_missing_directories():
        """Создать недостающие директории"""
        result = {
            'success': True,
            'directories_created': 0,
            'errors': []
        }
        
        try:
            integrity_report = FileSystemAdminHelpers.check_structure_integrity()
            
            for missing_dir in integrity_report['missing_directories']:
                try:
                    dir_path = Path(settings.MEDIA_ROOT) / missing_dir['path']
                    
                    if missing_dir['type'] == 'user':
                        DirectoryManager.create_user_directory(missing_dir['user_id'])
                    elif missing_dir['type'] == 'team':
                        DirectoryManager.create_team_directory(missing_dir['team_id'])
                    elif missing_dir['type'] == 'project':
                        project = Project.objects.get(id=missing_dir['project_id'])
                        DirectoryManager.create_project_directory(project.team.id, project.content_folder)
                    else:
                        DirectoryManager.ensure_directory_exists(dir_path)
                    
                    result['directories_created'] += 1
                    
                except Exception as e:
                    result['errors'].append({
                        'path': missing_dir['path'],
                        'error': str(e)
                    })
        
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        return result
    
    @staticmethod
    def get_available_management_actions():
        """Получить доступные действия управления"""
        actions = [
            {
                'id': 'cleanup_orphaned',
                'title': 'Очистить осиротевшие файлы',
                'description': 'Удалить файлы, которые не связаны с существующими объектами',
                'danger': True,
                'has_dry_run': True
            },
            {
                'id': 'fix_permissions',
                'title': 'Исправить права доступа',
                'description': 'Установить корректные права доступа для всех файлов и папок',
                'danger': False,
                'has_dry_run': False
            },
            {
                'id': 'validate_structure',
                'title': 'Проверить и исправить структуру',
                'description': 'Создать недостающие папки и исправить структуру файлов',
                'danger': False,
                'has_dry_run': False
            },
            {
                'id': 'create_missing_dirs',
                'title': 'Создать недостающие папки',
                'description': 'Создать все недостающие папки для пользователей, команд и проектов',
                'danger': False,
                'has_dry_run': False
            }
        ]
        
        return actions