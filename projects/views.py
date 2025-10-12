from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json
import os
import shutil
import zipfile
from io import BytesIO
from .models import Project, Chapter
from .forms import ProjectForm, ProjectEditForm


@login_required
def create_project(request):
    """Создание нового проекта (только из команды)"""
    # Получаем ID команды из URL параметра - ОБЯЗАТЕЛЬНО
    team_id = request.GET.get('team')
    
    if not team_id:
        messages.error(request, 'Проекты можно создавать только из команды.')
        return redirect('teams:team_list')
    
    # Проверяем доступ к команде
    try:
        from teams.models import Team
        selected_team = Team.objects.get(
            id=team_id,
            status='active',
            members=request.user
        )
    except Team.DoesNotExist:
        messages.error(request, 'Команда не найдена или у вас нет доступа к ней.')
        return redirect('teams:team_list')
    
    if request.method == 'POST':
        form = ProjectForm(user=request.user, selected_team=selected_team, data=request.POST)
        if form.is_valid():
            try:
                project = form.save()
                messages.success(request, f'Проект "{project.title}" успешно создан!')
                
                # Перенаправляем в команду
                return redirect('teams:team_detail', pk=project.team.id)
            except Exception as e:
                messages.error(request, f'Ошибка при создании проекта: {str(e)}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProjectForm(user=request.user, selected_team=selected_team)
    
    return render(request, 'projects/create_project.html', {
        'form': form,
        'selected_team': selected_team,
    })


@login_required
def project_detail(request, pk):
    """Детальная страница проекта"""
    project = get_object_or_404(Project, pk=pk)
    
    # Проверяем доступ через команду
    if not project.team.members.filter(id=request.user.id).exists():
        raise PermissionDenied("У вас нет доступа к этому проекту")
    
    # Получаем главы проекта
    chapters = project.chapters.all().order_by('id')
    
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'chapters': chapters,
    })


@login_required
def project_list(request):
    """Список проектов пользователя"""
    # Получаем проекты только из команд пользователя
    projects = Project.objects.filter(
        team__members=request.user,
        team__status='active'
    ).select_related('team').order_by('-created_at')
    
    return render(request, 'projects/project_list.html', {
        'projects': projects,
    })


@login_required
def edit_project(request, pk):
    """Редактирование проекта"""
    project = get_object_or_404(Project, pk=pk)
    
    # Проверяем права на редактирование
    if not project.team.members.filter(id=request.user.id).exists():
        raise PermissionDenied("У вас нет доступа к этому проекту")
    
    if request.method == 'POST':
        form = ProjectEditForm(data=request.POST, instance=project)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Проект успешно обновлен!')
                return redirect('projects:project_detail', pk=project.pk)
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении проекта: {str(e)}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProjectEditForm(instance=project)
    
    return render(request, 'projects/edit_project.html', {
        'form': form,
        'project': project,
    })


@login_required
@require_POST
def delete_project(request, pk):
    """Удаление проекта с полной очисткой данных"""
    from utils.file_system import FileCleanupManager, FileCleanupError
    
    project = get_object_or_404(Project, pk=pk)
    
    # Проверяем права на удаление (только члены команды)
    if not project.team.members.filter(id=request.user.id).exists():
        return JsonResponse({
            'success': False,
            'error': 'У вас нет прав на удаление этого проекта'
        }, status=403)
    
    try:
        project_title = project.title
        team_id = project.team.id
        content_folder = project.content_folder
        
        # Используем новую систему очистки файлов
        if content_folder:
            try:
                FileCleanupManager.cleanup_project_files(team_id, content_folder)
            except FileCleanupError as e:
                # Логируем ошибку, но не прерываем удаление проекта из БД
                print(f"Ошибка при очистке файлов проекта: {e}")
        
        # Удаляем проект из базы данных (каскадно удалятся все связанные объекты)
        project.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Проект "{project_title}" успешно удален',
            'redirect_url': f'/teams/{team_id}/'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при удалении проекта: {str(e)}'
        }, status=500)


@login_required
def download_project_data(request, pk):
    """Скачивание архива с данными проекта"""
    project = get_object_or_404(Project, pk=pk)
    
    # Проверяем доступ
    if not project.team.members.filter(id=request.user.id).exists():
        raise PermissionDenied("У вас нет доступа к этому проекту")
    
    try:
        # Создаем временный архив в памяти
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Добавляем информацию о проекте
            project_info = {
                'title': project.title,
                'description': project.description,
                'team': project.team.name,
                'project_type': project.get_project_type_display(),
                'age_rating': project.get_age_rating_display(),
                'status': project.get_status_display(),
                'created_at': project.created_at.isoformat(),
                'content_folder': project.content_folder,
            }
            
            # Добавляем информацию о главах
            chapters_data = []
            for chapter in project.chapters.all():
                chapter_info = {
                    'title': chapter.title,
                    'status': chapter.get_status_display(),
                    'assignee': chapter.assignee.username if chapter.assignee else None,
                    'created_at': chapter.created_at.isoformat(),
                }
                chapters_data.append(chapter_info)
            
            project_info['chapters'] = chapters_data
            
            # Сохраняем JSON с информацией о проекте
            zip_file.writestr('project_info.json', json.dumps(project_info, ensure_ascii=False, indent=2))
            
            # Добавляем файлы контента если папка существует
            if project.content_folder:
                from django.conf import settings
                content_path = os.path.join(settings.BASE_DIR, 'content', 'projects', str(project.team.id), project.content_folder)
                
                if os.path.exists(content_path):
                    for root, dirs, files in os.walk(content_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Получаем относительный путь для архива
                            arcname = os.path.relpath(file_path, content_path)
                            zip_file.write(file_path, f'content/{arcname}')
        
        zip_buffer.seek(0)
        
        # Создаем HTTP ответ с архивом
        response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
        filename = f"project_{project.id}_{project.title.replace(' ', '_')}.zip"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при создании архива: {str(e)}')
        return redirect('projects:edit_project', pk=pk)