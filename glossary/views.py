from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from projects.models import Project


@login_required
def glossary_list(request, project_id):
    """Список терминов глоссария для проекта"""
    project = get_object_or_404(Project, id=project_id, team__members=request.user)
    
    # Пока что заглушка - в будущем здесь будут термины
    terms = []
    
    return render(request, 'glossary/glossary_list.html', {
        'project': project,
        'terms': terms,
    })


@login_required
def glossary_create(request, project_id):
    """Создание нового термина (заглушка)"""
    project = get_object_or_404(Project, id=project_id, team__members=request.user)
    
    if request.method == 'POST':
        messages.info(request, 'Функция создания терминов пока не реализована.')
        return JsonResponse({'status': 'not_implemented'})
    
    return render(request, 'glossary/glossary_create.html', {
        'project': project,
    })


@login_required
def glossary_detail(request, project_id, pk):
    """Детали термина (заглушка)"""
    project = get_object_or_404(Project, id=project_id, team__members=request.user)
    
    return render(request, 'glossary/glossary_detail.html', {
        'project': project,
        'term_id': pk,
    })
