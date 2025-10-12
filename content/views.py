from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, FormView, ListView, View
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.conf import settings
import json
from datetime import datetime

from projects.models import Project
from .models import TextContent, ImageContent, ProjectDocument
from .forms import TextContentForm, ImageUploadForm, ProjectDocumentForm
from .middleware import ContentActionLogger
from .exceptions import ProjectAccessDenied, TextContentAccessDenied, ImageContentAccessDenied
from .error_handlers import ContentErrorMixin, graceful_content_fallback
from .performance import ContentQueryOptimizer, query_debugger, invalidate_user_cache


class ContentEditorView(LoginRequiredMixin, TemplateView):
    """Главная страница редактора контента"""
    template_name = 'content/editor.html'
    
    @query_debugger
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Используем оптимизированный класс для получения данных дашборда
        dashboard_data = ContentQueryOptimizer.get_dashboard_data_optimized(self.request.user)
        
        context.update({
            'projects': dashboard_data['projects'],
            'recent_texts': dashboard_data['recent_texts'],
            'stats': dashboard_data['stats']
        })
        return context


class TextEditorView(LoginRequiredMixin, ContentErrorMixin, FormView):
    """Редактор текстового контента"""
    template_name = 'content/text_editor.html'
    form_class = TextContentForm
    
    @query_debugger
    def get_object(self):
        """Получаем объект для редактирования если передан ID"""
        text_id = self.kwargs.get('text_id')
        if text_id:
            text_content = get_object_or_404(
                TextContent.objects.select_related('project__team', 'author'), 
                id=text_id
            )
            # Используем helper метод для проверки прав доступа
            if not text_content.user_can_edit(self.request.user):
                ContentActionLogger.log_access_denied(
                    self.request.user, 
                    'edit', 
                    'TextContent', 
                    text_content.id
                )
                raise TextContentAccessDenied(text_content.id)
            return text_content
        return None
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Если редактируем существующий текст
        text_content = self.get_object()
        if text_content:
            kwargs['instance'] = text_content
        
        return kwargs
    
    @query_debugger
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Используем оптимизированный класс для получения проектов пользователя
        user_projects = ContentQueryOptimizer.get_user_projects_optimized(self.request.user)
        
        context.update({
            'projects': user_projects,
            'text_content': self.get_object(),
        })
        return context
    
    def form_valid(self, form):
        # Определяем, создаем ли новый текст или обновляем существующий
        is_new = not form.instance.pk
        
        # Отслеживаем изменения для логирования
        changed_fields = []
        if not is_new:
            original = TextContent.objects.get(pk=form.instance.pk)
            for field in form.changed_data:
                if field in ['title', 'content', 'is_draft']:
                    changed_fields.append(field)
        
        text_content = form.save(commit=False)
        text_content.author = self.request.user
        text_content.save()
        
        # Инвалидируем кэш пользователя при изменении данных
        invalidate_user_cache(self.request.user.id)
        
        # Логируем действие
        if is_new:
            ContentActionLogger.log_text_created(self.request.user, text_content)
        else:
            ContentActionLogger.log_text_updated(self.request.user, text_content, changed_fields)
        
        messages.success(self.request, 'Текст успешно сохранен!')
        return redirect('content:text_editor', text_id=text_content.id)
    
    def get_success_url(self):
        return self.request.path


class ImageGalleryView(LoginRequiredMixin, ContentErrorMixin, ListView):
    """Галерея изображений проекта"""
    template_name = 'content/image_gallery.html'
    context_object_name = 'images'
    paginate_by = 20
    
    @query_debugger
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(
            Project.objects.select_related('team'), 
            id=project_id
        )
        
        # Используем helper метод для проверки прав доступа
        if not project.user_has_access(self.request.user):
            ContentActionLogger.log_access_denied(
                self.request.user, 
                'view_images', 
                'Project', 
                project.id
            )
            raise ProjectAccessDenied(project.id)
        
        return ContentQueryOptimizer.get_project_images_optimized(project)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        context['project'] = get_object_or_404(
            Project.objects.select_related('team'), 
            id=project_id
        )
        return context


class ImageUploadView(LoginRequiredMixin, ContentErrorMixin, FormView):
    """Загрузка изображений проекта"""
    template_name = 'content/image_upload.html'
    form_class = ImageUploadForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        from utils.file_system import DirectoryManager, FileUploadError
        
        try:
            # Создаем папку проекта если не существует
            project = form.cleaned_data['project']
            DirectoryManager.create_project_directory(project.team.id, project.content_folder)
            
            # Сохраняем изображение
            image = form.save(commit=False)
            image.uploader = self.request.user
            image.save()
            
            messages.success(self.request, 'Изображение успешно загружено!')
            return redirect('content:image_gallery', project_id=project.id)
            
        except FileUploadError as e:
            messages.error(self.request, f"Ошибка загрузки изображения: {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, "Произошла ошибка при загрузке изображения")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        if project_id:
            context['project'] = get_object_or_404(
                Project.objects.select_related('team'), 
                id=project_id
            )
        return context


@method_decorator(csrf_exempt, name='dispatch')
class AutosaveView(LoginRequiredMixin, View):
    """API для автосохранения текста"""
    
    @query_debugger
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            title = data.get('title', '')
            content = data.get('content', '')
            text_id = data.get('text_id')
            
            if not text_id:
                return JsonResponse({'error': 'Не указан ID текста'}, status=400)
            
            # Обновляем существующий текст с оптимизированным запросом
            text_content = get_object_or_404(
                TextContent.objects.select_related('project__team', 'author'), 
                id=text_id
            )
            
            # Используем helper метод для проверки прав доступа
            if not text_content.user_can_edit(request.user):
                ContentActionLogger.log_access_denied(
                    request.user, 
                    'autosave', 
                    'TextContent', 
                    text_content.id
                )
                return JsonResponse({
                    'error': True,
                    'message': 'Нет доступа к редактированию этого текста',
                    'error_type': 'access_denied',
                    'redirect_url': '/content/'
                }, status=403)
            
            # Обновляем поля draft_content и last_autosave
            text_content.draft_content = content
            text_content.last_autosave = datetime.now()
            text_content.save(update_fields=['draft_content', 'last_autosave'])
            
            # Инвалидируем кэш пользователя при автосохранении
            invalidate_user_cache(request.user.id)
            
            # Логируем автосохранение
            ContentActionLogger.log_text_autosaved(request.user, text_content)
            
            return JsonResponse({
                'success': True,
                'last_autosave': text_content.last_autosave.strftime('%H:%M:%S')
            })
        
        except json.JSONDecodeError:
            return JsonResponse({
                'error': True,
                'message': 'Неверный формат JSON',
                'error_type': 'invalid_json'
            }, status=400)
        except TextContentAccessDenied as e:
            return JsonResponse({
                'error': True,
                'message': str(e),
                'error_type': 'access_denied',
                'redirect_url': '/content/'
            }, status=403)
        except Exception as e:
            return JsonResponse({
                'error': True,
                'message': 'Произошла ошибка при автосохранении',
                'error_type': 'server_error',
                'details': str(e) if settings.DEBUG else None
            }, status=500)


@login_required
@query_debugger
def create_project(request):
    """Создание нового проекта"""
    # Получаем ID команды из URL параметра
    team_id = request.GET.get('team')
    selected_team = None
    
    if team_id:
        try:
            from teams.models import Team
            selected_team = Team.objects.get(
                id=team_id,
                status='active',
                teammembership__user=request.user,
                teammembership__is_active=True
            )
        except Team.DoesNotExist:
            messages.error(request, 'Команда не найдена или у вас нет доступа к ней.')
            return redirect('teams:team_list')
    
    if request.method == 'POST':
        form = ProjectForm(user=request.user, data=request.POST)
        if form.is_valid():
            try:
                project = form.save()
                
                # Инвалидируем кэш пользователя при создании проекта
                invalidate_user_cache(request.user.id)
                
                # Логируем создание проекта
                ContentActionLogger.log_project_created(request.user, project)
                
                messages.success(request, f'Проект "{project.name}" успешно создан!')
                
                # Перенаправляем обратно в команду, если проект создавался из команды
                if project.team:
                    return redirect('teams:team_detail', pk=project.team.id)
                else:
                    return redirect('/projects/')
            except Exception as e:
                messages.error(request, f'Ошибка при создании проекта: {str(e)}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ProjectForm(user=request.user)
        
        # Предзаполняем команду, если она была передана в URL
        if selected_team:
            form.fields['team'].initial = selected_team
    
    context = {
        'form': form,
        'selected_team': selected_team,
    }
    
    return render(request, 'content/create_project.html', context)


@login_required
@query_debugger
def project_texts(request, project_id):
    """Список текстов проекта с пагинацией и поиском"""
    from django.core.paginator import Paginator
    
    project = get_object_or_404(
        Project.objects.select_related('team'), 
        id=project_id
    )
    
    # Используем helper метод для проверки прав доступа
    if not project.user_has_access(request.user):
        ContentActionLogger.log_access_denied(
            request.user, 
            'view_texts', 
            'Project', 
            project.id
        )
        raise ProjectAccessDenied(project.id)
    
    # Поиск по заголовкам
    search_query = request.GET.get('search', '').strip()
    
    # Получаем тексты проекта с оптимизированными запросами
    texts = ContentQueryOptimizer.get_project_texts_optimized(project, search_query)
    
    # Пагинация
    paginator = Paginator(texts, 10)  # 10 текстов на страницу
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'content/project_texts.html', {
        'project': project,
        'texts': page_obj,
        'search_query': search_query,
        'page_obj': page_obj,
    })


@login_required
def content_not_found(request):
    """Представление для случаев, когда контент не найден"""
    return graceful_content_fallback(request, 'general')


class ProjectDocumentUploadView(LoginRequiredMixin, ContentErrorMixin, FormView):
    """Загрузка документов проекта"""
    template_name = 'content/document_upload.html'
    form_class = ProjectDocumentForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        from utils.file_system import DirectoryManager, FileUploadError
        
        try:
            # Создаем папку проекта если не существует
            project = form.cleaned_data['project']
            DirectoryManager.create_project_directory(project.team.id, project.content_folder)
            
            # Сохраняем документ
            document = form.save(commit=False)
            document.uploaded_by = self.request.user
            document.save()
            
            messages.success(self.request, 'Документ успешно загружен!')
            return redirect('content:project_documents', project_id=project.id)
            
        except FileUploadError as e:
            messages.error(self.request, f"Ошибка загрузки документа: {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, "Произошла ошибка при загрузке документа")
            return self.form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        if project_id:
            context['project'] = get_object_or_404(
                Project.objects.select_related('team'), 
                id=project_id
            )
        return context


class ProjectDocumentListView(LoginRequiredMixin, ContentErrorMixin, ListView):
    """Список документов проекта"""
    template_name = 'content/project_documents.html'
    context_object_name = 'documents'
    paginate_by = 20
    
    @query_debugger
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(
            Project.objects.select_related('team'), 
            id=project_id
        )
        
        # Проверяем права доступа
        if not project.user_has_access(self.request.user):
            ContentActionLogger.log_access_denied(
                self.request.user, 
                'view_documents', 
                'Project', 
                project.id
            )
            raise ProjectAccessDenied(project.id)
        
        return project.documents.select_related('uploaded_by').order_by('-uploaded_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project_id = self.kwargs.get('project_id')
        context['project'] = get_object_or_404(
            Project.objects.select_related('team'), 
            id=project_id
        )
        return context


def custom_403_handler(request, exception=None):
    """Кастомный обработчик 403 ошибок для приложения content"""
    from .error_handlers import handle_content_permission_denied
    
    # Если это наше исключение, используем специальный обработчик
    if isinstance(exception, (ProjectAccessDenied, TextContentAccessDenied, ImageContentAccessDenied)):
        return handle_content_permission_denied(request, exception)
    
    # Иначе используем стандартную обработку
    return render(request, 'content/errors/403.html', {
        'error_message': 'У вас нет доступа к этой странице',
        'suggestions': [
            'Убедитесь, что вы вошли в систему',
            'Проверьте, что у вас есть необходимые права',
            'Обратитесь к администратору за помощью'
        ],
        'back_url': request.META.get('HTTP_REFERER', '/content/')
    }, status=403)