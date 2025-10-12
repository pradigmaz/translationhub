"""
Миксины и декораторы для проверки разрешений в системе управления ролями TranslationHub.

Этот модуль содержит миксины для class-based views и декораторы для function-based views,
которые обеспечивают проверку разрешений пользователей в командах на основе их ролей.
"""

import logging
from functools import wraps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import Http404
from .models import Team
from .permission_checker import RolePermissionChecker

logger = logging.getLogger(__name__)


class TeamPermissionRequiredMixin(LoginRequiredMixin):
    """
    Миксин для проверки разрешений пользователя в команде.

    Этот миксин автоматически проверяет, имеет ли текущий пользователь
    необходимое разрешение в команде перед выполнением представления.

    Attributes:
        required_team_permission (str): Кодовое имя требуемого разрешения
        team_url_kwarg (str): Имя параметра URL для получения ID команды (по умолчанию 'team_id')
        permission_denied_message (str): Сообщение об ошибке при отсутствии разрешения
        raise_404_on_no_permission (bool): Возвращать 404 вместо 403 при отсутствии разрешения

    Examples:
        >>> class ProjectCreateView(TeamPermissionRequiredMixin, CreateView):
        ...     required_team_permission = 'can_create_project'
        ...     model = Project
        ...     template_name = 'projects/create.html'
    """

    required_team_permission = None
    team_url_kwarg = "team_id"
    permission_denied_message = (
        "У вас нет прав для выполнения этого действия в данной команде."
    )
    raise_404_on_no_permission = False

    def get_team(self):
        """
        Получает объект команды из URL параметров.

        Returns:
            Team: Объект команды

        Raises:
            Http404: Если команда не найдена
        """
        team_id = self.kwargs.get(self.team_url_kwarg)
        if not team_id:
            logger.error(f"Параметр {self.team_url_kwarg} не найден в URL")
            raise Http404("Команда не найдена")

        return get_object_or_404(Team, pk=team_id)

    def get_required_permission(self):
        """
        Получает требуемое разрешение.

        Returns:
            str: Кодовое имя разрешения

        Raises:
            ValueError: Если разрешение не указано
        """
        if not self.required_team_permission:
            raise ValueError(
                f"{self.__class__.__name__} должен определять required_team_permission"
            )
        return self.required_team_permission

    def check_team_permission(self, user, team, permission):
        """
        Проверяет разрешение пользователя в команде.

        Args:
            user: Объект пользователя
            team: Объект команды
            permission (str): Кодовое имя разрешения

        Returns:
            bool: True если разрешение есть
        """
        return RolePermissionChecker.user_has_team_permission(user, team, permission)

    def handle_no_permission(self):
        """
        Обрабатывает отсутствие разрешения.

        Raises:
            PermissionDenied или Http404: В зависимости от настроек
        """
        if self.raise_404_on_no_permission:
            raise Http404("Страница не найдена")
        else:
            raise PermissionDenied(self.permission_denied_message)

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяет разрешения перед выполнением представления.

        Args:
            request: HTTP запрос
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            HttpResponse: Ответ представления

        Raises:
            PermissionDenied или Http404: При отсутствии разрешения
        """
        # Сначала проверяем аутентификацию
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        try:
            team = self.get_team()
            permission = self.get_required_permission()

            # Проверяем разрешение
            if not self.check_team_permission(request.user, team, permission):
                logger.warning(
                    f"Пользователь {request.user.username} попытался получить доступ "
                    f"к {self.__class__.__name__} без разрешения {permission} "
                    f"в команде {team.name}"
                )
                return self.handle_no_permission()

            # Сохраняем команду в атрибуте для использования в представлении
            self.team = team

            logger.debug(
                f"Пользователь {request.user.username} получил доступ к {self.__class__.__name__} "
                f"с разрешением {permission} в команде {team.name}"
            )

            return super().dispatch(request, *args, **kwargs)

        except Http404:
            # Перебрасываем 404 как есть
            raise
        except Exception as e:
            logger.error(
                f"Ошибка при проверке разрешений в {self.__class__.__name__}: {str(e)}"
            )
            return self.handle_no_permission()

    def get_context_data(self, **kwargs):
        """
        Добавляет команду в контекст шаблона.

        Args:
            **kwargs: Дополнительные аргументы контекста

        Returns:
            dict: Контекст шаблона
        """
        context = super().get_context_data(**kwargs)
        if hasattr(self, "team"):
            context["team"] = self.team
        return context


class MultipleTeamPermissionRequiredMixin(LoginRequiredMixin):
    """
    Миксин для проверки нескольких разрешений пользователя в команде.

    Позволяет проверять несколько разрешений одновременно с логикой AND или OR.

    Attributes:
        required_team_permissions (list): Список кодовых имен требуемых разрешений
        require_all_permissions (bool): True для логики AND, False для OR (по умолчанию True)
        team_url_kwarg (str): Имя параметра URL для получения ID команды
        permission_denied_message (str): Сообщение об ошибке при отсутствии разрешения
        raise_404_on_no_permission (bool): Возвращать 404 вместо 403 при отсутствии разрешения

    Examples:
        >>> class ProjectManageView(MultipleTeamPermissionRequiredMixin, UpdateView):
        ...     required_team_permissions = ['can_manage_project', 'can_edit_content']
        ...     require_all_permissions = True  # Нужны ОБА разрешения
        ...     model = Project

        >>> class ContentEditView(MultipleTeamPermissionRequiredMixin, UpdateView):
        ...     required_team_permissions = ['can_edit_content', 'can_review_content']
        ...     require_all_permissions = False  # Достаточно ЛЮБОГО разрешения
        ...     model = Content
    """

    required_team_permissions = []
    require_all_permissions = True  # True = AND, False = OR
    team_url_kwarg = "team_id"
    permission_denied_message = (
        "У вас нет необходимых прав для выполнения этого действия в данной команде."
    )
    raise_404_on_no_permission = False

    def get_team(self):
        """
        Получает объект команды из URL параметров.

        Returns:
            Team: Объект команды

        Raises:
            Http404: Если команда не найдена
        """
        team_id = self.kwargs.get(self.team_url_kwarg)
        if not team_id:
            logger.error(f"Параметр {self.team_url_kwarg} не найден в URL")
            raise Http404("Команда не найдена")

        return get_object_or_404(Team, pk=team_id)

    def get_required_permissions(self):
        """
        Получает список требуемых разрешений.

        Returns:
            list: Список кодовых имен разрешений

        Raises:
            ValueError: Если разрешения не указаны
        """
        if not self.required_team_permissions:
            raise ValueError(
                f"{self.__class__.__name__} должен определять required_team_permissions"
            )
        return self.required_team_permissions

    def check_team_permissions(self, user, team, permissions):
        """
        Проверяет разрешения пользователя в команде.

        Args:
            user: Объект пользователя
            team: Объект команды
            permissions (list): Список кодовых имен разрешений

        Returns:
            bool: True если условие разрешений выполнено
        """
        if self.require_all_permissions:
            # Логика AND - нужны ВСЕ разрешения
            return RolePermissionChecker.user_has_all_team_permissions(
                user, team, permissions
            )
        else:
            # Логика OR - достаточно ЛЮБОГО разрешения
            return RolePermissionChecker.user_has_any_team_permission(
                user, team, permissions
            )

    def handle_no_permission(self):
        """
        Обрабатывает отсутствие разрешения.

        Raises:
            PermissionDenied или Http404: В зависимости от настроек
        """
        if self.raise_404_on_no_permission:
            raise Http404("Страница не найдена")
        else:
            raise PermissionDenied(self.permission_denied_message)

    def dispatch(self, request, *args, **kwargs):
        """
        Проверяет разрешения перед выполнением представления.

        Args:
            request: HTTP запрос
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            HttpResponse: Ответ представления

        Raises:
            PermissionDenied или Http404: При отсутствии разрешения
        """
        # Сначала проверяем аутентификацию
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        try:
            team = self.get_team()
            permissions = self.get_required_permissions()

            # Проверяем разрешения
            if not self.check_team_permissions(request.user, team, permissions):
                logic_type = "ALL" if self.require_all_permissions else "ANY"
                logger.warning(
                    f"Пользователь {request.user.username} попытался получить доступ "
                    f"к {self.__class__.__name__} без необходимых разрешений ({logic_type} из {permissions}) "
                    f"в команде {team.name}"
                )
                return self.handle_no_permission()

            # Сохраняем команду в атрибуте для использования в представлении
            self.team = team

            logic_type = "ALL" if self.require_all_permissions else "ANY"
            logger.debug(
                f"Пользователь {request.user.username} получил доступ к {self.__class__.__name__} "
                f"с необходимыми разрешениями ({logic_type} из {permissions}) в команде {team.name}"
            )

            return super().dispatch(request, *args, **kwargs)

        except Http404:
            # Перебрасываем 404 как есть
            raise
        except Exception as e:
            logger.error(
                f"Ошибка при проверке разрешений в {self.__class__.__name__}: {str(e)}"
            )
            return self.handle_no_permission()

    def get_context_data(self, **kwargs):
        """
        Добавляет команду в контекст шаблона.

        Args:
            **kwargs: Дополнительные аргументы контекста

        Returns:
            dict: Контекст шаблона
        """
        context = super().get_context_data(**kwargs)
        if hasattr(self, "team"):
            context["team"] = self.team
        return context


# Декораторы для function-based views


def team_permission_required(
    permission,
    team_url_kwarg="team_id",
    permission_denied_message=None,
    raise_404=False,
):
    """
    Декоратор для проверки разрешения пользователя в команде.

    Args:
        permission (str): Кодовое имя требуемого разрешения
        team_url_kwarg (str): Имя параметра URL для получения ID команды
        permission_denied_message (str): Пользовательское сообщение об ошибке
        raise_404 (bool): Возвращать 404 вместо 403 при отсутствии разрешения

    Returns:
        function: Декорированная функция

    Examples:
        >>> @team_permission_required('can_create_project')
        ... def create_project(request, team_id):
        ...     # Логика создания проекта
        ...     pass

        >>> @team_permission_required('can_manage_team', raise_404=True)
        ... def manage_team(request, team_id):
        ...     # Логика управления командой
        ...     pass
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Проверяем аутентификацию
            if not request.user.is_authenticated:
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Необходима аутентификация")

            try:
                # Получаем ID команды из параметров
                team_id = kwargs.get(team_url_kwarg)
                if not team_id:
                    logger.error(f"Параметр {team_url_kwarg} не найден в URL")
                    raise Http404("Команда не найдена")

                # Получаем команду
                team = get_object_or_404(Team, pk=team_id)

                # Проверяем разрешение
                if not RolePermissionChecker.user_has_team_permission(
                    request.user, team, permission
                ):
                    logger.warning(
                        f"Пользователь {request.user.username} попытался получить доступ "
                        f"к {view_func.__name__} без разрешения {permission} "
                        f"в команде {team.name}"
                    )

                    if raise_404:
                        raise Http404("Страница не найдена")
                    else:
                        message = (
                            permission_denied_message
                            or "У вас нет прав для выполнения этого действия в данной команде."
                        )
                        raise PermissionDenied(message)

                logger.debug(
                    f"Пользователь {request.user.username} получил доступ к {view_func.__name__} "
                    f"с разрешением {permission} в команде {team.name}"
                )

                # Добавляем команду в request для использования в представлении
                request.team = team

                return view_func(request, *args, **kwargs)

            except Http404:
                # Перебрасываем 404 как есть
                raise
            except PermissionDenied:
                # Перебрасываем PermissionDenied как есть (с оригинальным сообщением)
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка при проверке разрешения {permission} в {view_func.__name__}: {str(e)}"
                )
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Ошибка проверки разрешений")

        return wrapper

    return decorator


def any_team_permission_required(
    *permissions,
    team_url_kwarg="team_id",
    permission_denied_message=None,
    raise_404=False,
):
    """
    Декоратор для проверки любого из указанных разрешений пользователя в команде.

    Args:
        *permissions: Кодовые имена разрешений (нужно любое из них)
        team_url_kwarg (str): Имя параметра URL для получения ID команды
        permission_denied_message (str): Пользовательское сообщение об ошибке
        raise_404 (bool): Возвращать 404 вместо 403 при отсутствии разрешения

    Returns:
        function: Декорированная функция

    Examples:
        >>> @any_team_permission_required('can_edit_content', 'can_review_content')
        ... def edit_content(request, team_id):
        ...     # Логика редактирования контента
        ...     pass
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Проверяем аутентификацию
            if not request.user.is_authenticated:
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Необходима аутентификация")

            if not permissions:
                logger.error(
                    f"Не указаны разрешения для декоратора в {view_func.__name__}"
                )
                raise ValueError("Необходимо указать хотя бы одно разрешение")

            try:
                # Получаем ID команды из параметров
                team_id = kwargs.get(team_url_kwarg)
                if not team_id:
                    logger.error(f"Параметр {team_url_kwarg} не найден в URL")
                    raise Http404("Команда не найдена")

                # Получаем команду
                team = get_object_or_404(Team, pk=team_id)

                # Проверяем любое из разрешений
                if not RolePermissionChecker.user_has_any_team_permission(
                    request.user, team, permissions
                ):
                    logger.warning(
                        f"Пользователь {request.user.username} попытался получить доступ "
                        f"к {view_func.__name__} без любого из разрешений {permissions} "
                        f"в команде {team.name}"
                    )

                    if raise_404:
                        raise Http404("Страница не найдена")
                    else:
                        message = (
                            permission_denied_message
                            or "У вас нет необходимых прав для выполнения этого действия в данной команде."
                        )
                        raise PermissionDenied(message)

                logger.debug(
                    f"Пользователь {request.user.username} получил доступ к {view_func.__name__} "
                    f"с одним из разрешений {permissions} в команде {team.name}"
                )

                # Добавляем команду в request для использования в представлении
                request.team = team

                return view_func(request, *args, **kwargs)

            except Http404:
                # Перебрасываем 404 как есть
                raise
            except PermissionDenied:
                # Перебрасываем PermissionDenied как есть (с оригинальным сообщением)
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка при проверке разрешений {permissions} в {view_func.__name__}: {str(e)}"
                )
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Ошибка проверки разрешений")

        return wrapper

    return decorator


def all_team_permissions_required(
    *permissions,
    team_url_kwarg="team_id",
    permission_denied_message=None,
    raise_404=False,
):
    """
    Декоратор для проверки всех указанных разрешений пользователя в команде.

    Args:
        *permissions: Кодовые имена разрешений (нужны все)
        team_url_kwarg (str): Имя параметра URL для получения ID команды
        permission_denied_message (str): Пользовательское сообщение об ошибке
        raise_404 (bool): Возвращать 404 вместо 403 при отсутствии разрешения

    Returns:
        function: Декорированная функция

    Examples:
        >>> @all_team_permissions_required('can_manage_project', 'can_delete_project')
        ... def delete_project(request, team_id, project_id):
        ...     # Логика удаления проекта
        ...     pass
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Проверяем аутентификацию
            if not request.user.is_authenticated:
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Необходима аутентификация")

            if not permissions:
                logger.error(
                    f"Не указаны разрешения для декоратора в {view_func.__name__}"
                )
                raise ValueError("Необходимо указать хотя бы одно разрешение")

            try:
                # Получаем ID команды из параметров
                team_id = kwargs.get(team_url_kwarg)
                if not team_id:
                    logger.error(f"Параметр {team_url_kwarg} не найден в URL")
                    raise Http404("Команда не найдена")

                # Получаем команду
                team = get_object_or_404(Team, pk=team_id)

                # Проверяем все разрешения
                if not RolePermissionChecker.user_has_all_team_permissions(
                    request.user, team, permissions
                ):
                    logger.warning(
                        f"Пользователь {request.user.username} попытался получить доступ "
                        f"к {view_func.__name__} без всех разрешений {permissions} "
                        f"в команде {team.name}"
                    )

                    if raise_404:
                        raise Http404("Страница не найдена")
                    else:
                        message = (
                            permission_denied_message
                            or "У вас нет всех необходимых прав для выполнения этого действия в данной команде."
                        )
                        raise PermissionDenied(message)

                logger.debug(
                    f"Пользователь {request.user.username} получил доступ к {view_func.__name__} "
                    f"со всеми разрешениями {permissions} в команде {team.name}"
                )

                # Добавляем команду в request для использования в представлении
                request.team = team

                return view_func(request, *args, **kwargs)

            except Http404:
                # Перебрасываем 404 как есть
                raise
            except PermissionDenied:
                # Перебрасываем PermissionDenied как есть (с оригинальным сообщением)
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка при проверке разрешений {permissions} в {view_func.__name__}: {str(e)}"
                )
                if raise_404:
                    raise Http404("Страница не найдена")
                else:
                    raise PermissionDenied("Ошибка проверки разрешений")

        return wrapper

    return decorator
