// static/js/main.js - Bootstrap 5 Custom JavaScript

document.addEventListener("DOMContentLoaded", function () {
  // Инициализация всех Bootstrap компонентов

  // Bootstrap 5 автоматически инициализирует dropdown при наличии data-bs-toggle="dropdown"
  // Никакой дополнительной инициализации не требуется

  // Автоматическое скрытие алертов через 5 секунд
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  // Добавление анимации появления для карточек
  const cards = document.querySelectorAll(".card");
  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.style.opacity = "1";
        entry.target.style.transform = "translateY(0)";
      }
    });
  });

  cards.forEach(function (card) {
    card.style.opacity = "0";
    card.style.transform = "translateY(20px)";
    card.style.transition = "opacity 0.5s ease, transform 0.5s ease";
    observer.observe(card);
  });

  // Bootstrap 5 автоматически инициализирует dropdown при наличии data-bs-toggle="dropdown"
  // Дополнительная инициализация не требуется

  // Инициализация навигации между разделами личного кабинета
  initDashboardNavigation();

  // Инициализация предварительного просмотра аватарки
  initAvatarPreview();
});

// Функция для инициализации навигации в личном кабинете
function initDashboardNavigation() {
  const navTabs = document.querySelectorAll(".nav-tabs .nav-link");
  const navPills = document.querySelectorAll(".nav-pills .nav-link");

  // Обработка Bootstrap nav-tabs
  navTabs.forEach(function (tab) {
    tab.addEventListener("click", function (e) {
      e.preventDefault();

      // Удаляем активный класс со всех табов
      navTabs.forEach(function (t) {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });

      // Добавляем активный класс к текущему табу
      this.classList.add("active");
      this.setAttribute("aria-selected", "true");

      // Если есть data-bs-target, переключаем контент
      const target = this.getAttribute("data-bs-target");
      if (target) {
        const tabContent = document.querySelectorAll(".tab-pane");
        tabContent.forEach(function (pane) {
          pane.classList.remove("show", "active");
        });

        const targetPane = document.querySelector(target);
        if (targetPane) {
          targetPane.classList.add("show", "active");
        }
      }
    });
  });

  // Обработка Bootstrap nav-pills
  navPills.forEach(function (pill) {
    pill.addEventListener("click", function (e) {
      e.preventDefault();

      // Удаляем активный класс со всех pills
      navPills.forEach(function (p) {
        p.classList.remove("active");
      });

      // Добавляем активный класс к текущему pill
      this.classList.add("active");
    });
  });
}

// Функция для программного переключения табов
function switchToTab(tabId) {
  const tab = document.querySelector(`[data-bs-target="${tabId}"]`);
  if (tab) {
    tab.click();
  }
}

// Функция для установки активного раздела навигации
function setActiveNavItem(selector) {
  // Удаляем активный класс со всех элементов навигации
  const navItems = document.querySelectorAll(".nav-link");
  navItems.forEach(function (item) {
    item.classList.remove("active");
  });

  // Добавляем активный класс к указанному элементу
  const activeItem = document.querySelector(selector);
  if (activeItem) {
    activeItem.classList.add("active");
  }
}

// Функция для инициализации предварительного просмотра аватарки
function initAvatarPreview() {
  const avatarInput = document.querySelector("#id_avatar");
  const avatarPreview = document.querySelector("#avatar-preview");
  const avatarPreviewImg = document.querySelector("#avatar-preview-img");
  const avatarPlaceholder = document.querySelector("#avatar-placeholder");

  if (avatarInput) {
    avatarInput.addEventListener("change", function (e) {
      const file = e.target.files[0];

      if (file) {
        // Проверка типа файла
        if (!file.type.match("image/jpeg") && !file.type.match("image/png")) {
          alert("Поддерживаются только JPG и PNG файлы");
          this.value = "";
          return;
        }

        // Проверка размера файла (2MB)
        if (file.size > 2 * 1024 * 1024) {
          alert("Размер файла не должен превышать 2MB");
          this.value = "";
          return;
        }

        // Создание предварительного просмотра
        const reader = new FileReader();
        reader.onload = function (e) {
          if (avatarPreviewImg) {
            avatarPreviewImg.src = e.target.result;
            avatarPreviewImg.style.display = "block";
          }
          if (avatarPlaceholder) {
            avatarPlaceholder.style.display = "none";
          }
          if (avatarPreview) {
            avatarPreview.style.display = "block";
          }
        };
        reader.readAsDataURL(file);
      } else {
        // Скрываем предварительный просмотр если файл не выбран
        if (avatarPreviewImg) {
          avatarPreviewImg.style.display = "none";
        }
        if (avatarPlaceholder) {
          avatarPlaceholder.style.display = "block";
        }
      }
    });
  }
}

// Функция для валидации загружаемой аватарки
function validateAvatarFile(file) {
  const errors = [];

  // Проверка типа файла
  if (!file.type.match("image/jpeg") && !file.type.match("image/png")) {
    errors.push("Поддерживаются только JPG и PNG файлы");
  }

  // Проверка размера файла (2MB)
  if (file.size > 2 * 1024 * 1024) {
    errors.push("Размер файла не должен превышать 2MB");
  }

  return errors;
}

// Утилитарные функции для работы с Bootstrap 5.3 модальными окнами
function showBootstrapModal(modalId, options = {}) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) {
    const modal = new bootstrap.Modal(modalElement, options);
    modal.show();
    return modal;
  }
  return null;
}

function hideBootstrapModal(modalId) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) {
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
      modal.hide();
    }
  }
}

// Функция для показа уведомлений с Bootstrap 5.3 toast
function showToast(message, type = 'info', duration = 5000) {
  // Создаем контейнер для toast если его нет
  let toastContainer = document.querySelector('.toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = '1055';
    document.body.appendChild(toastContainer);
  }

  // Определяем цвет и иконку в зависимости от типа
  let bgClass = 'text-bg-primary';
  let iconClass = 'fa-info-circle';
  
  switch(type) {
    case 'success':
      bgClass = 'text-bg-success';
      iconClass = 'fa-check-circle';
      break;
    case 'error':
    case 'danger':
      bgClass = 'text-bg-danger';
      iconClass = 'fa-exclamation-circle';
      break;
    case 'warning':
      bgClass = 'text-bg-warning';
      iconClass = 'fa-exclamation-triangle';
      break;
  }

  // Создаем toast элемент
  const toastId = 'toast-' + Date.now();
  const toastHTML = `
    <div class="toast ${bgClass}" role="alert" aria-live="assertive" aria-atomic="true" id="${toastId}">
      <div class="toast-header">
        <i class="fas ${iconClass} me-2"></i>
        <strong class="me-auto">Уведомление</strong>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Закрыть"></button>
      </div>
      <div class="toast-body">
        ${message}
      </div>
    </div>
  `;

  toastContainer.insertAdjacentHTML('beforeend', toastHTML);
  
  // Инициализируем и показываем toast
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement, {
    delay: duration
  });
  
  toast.show();
  
  // Удаляем элемент после скрытия
  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.remove();
  });
  
  return toast;
}

// Функция для анимации элементов с использованием Bootstrap 5.3 классов
function animateElement(element, animationType = 'pulse') {
  if (!element) return;
  
  const animations = {
    pulse: 'animate__pulse',
    bounce: 'animate__bounce',
    shake: 'animate__shakeX',
    fadeIn: 'animate__fadeIn',
    slideIn: 'animate__slideInDown'
  };
  
  const animationClass = animations[animationType] || animations.pulse;
  
  // Добавляем базовые классы animate.css если они не подключены
  element.style.animationDuration = '0.5s';
  element.style.animationFillMode = 'both';
  
  // Простая CSS анимация без внешних библиотек
  switch(animationType) {
    case 'pulse':
      element.style.transform = 'scale(1.05)';
      element.style.transition = 'transform 0.15s ease-in-out';
      setTimeout(() => {
        element.style.transform = 'scale(1)';
      }, 150);
      break;
    case 'shake':
      element.style.animation = 'shake 0.5s ease-in-out';
      break;
    case 'fadeIn':
      element.style.opacity = '0';
      element.style.transition = 'opacity 0.3s ease-in-out';
      setTimeout(() => {
        element.style.opacity = '1';
      }, 10);
      break;
  }
}

// CSS для анимации shake
const shakeKeyframes = `
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}
`;

// Добавляем стили анимации в head
if (!document.querySelector('#shake-animation-styles')) {
  const style = document.createElement('style');
  style.id = 'shake-animation-styles';
  style.textContent = shakeKeyframes;
  document.head.appendChild(style);
}

// Глобальные функции для работы с Bootstrap 5.3 модальными окнами
window.TeamModals = {
  // Показать модальное окно подтверждения
  showConfirmModal: function(title, message, onConfirm, options = {}) {
    const modalId = 'dynamicConfirmModal';
    let modal = document.getElementById(modalId);
    
    if (!modal) {
      modal = this.createConfirmModal(modalId);
    }
    
    const modalTitle = modal.querySelector('.modal-title');
    const modalMessage = modal.querySelector('.modal-body p');
    const confirmBtn = modal.querySelector('.btn-primary');
    
    modalTitle.innerHTML = `<i class="fas fa-question-circle me-2"></i>${title}`;
    modalMessage.textContent = message;
    
    // Настройка кнопки подтверждения
    const btnClass = options.type === 'danger' ? 'btn-danger' : 
                    options.type === 'warning' ? 'btn-warning' : 'btn-primary';
    confirmBtn.className = `btn ${btnClass}`;
    confirmBtn.innerHTML = `<i class="fas fa-check me-1"></i>${options.confirmText || 'Подтвердить'}`;
    
    // Обработчик подтверждения
    confirmBtn.onclick = function() {
      const bootstrapModal = bootstrap.Modal.getInstance(modal);
      bootstrapModal.hide();
      if (onConfirm) onConfirm();
    };
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    return bootstrapModal;
  },
  
  // Создать модальное окно подтверждения
  createConfirmModal: function(modalId) {
    const modalHTML = `
      <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content border-0 shadow">
            <div class="modal-header border-0">
              <h5 class="modal-title fw-bold"></h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
              <p class="mb-0"></p>
            </div>
            <div class="modal-footer border-0">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                <i class="fas fa-times me-1"></i>Отмена
              </button>
              <button type="button" class="btn btn-primary">
                <i class="fas fa-check me-1"></i>Подтвердить
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    return document.getElementById(modalId);
  },
  
  // Показать модальное окно загрузки
  showLoadingModal: function(message = 'Загрузка...') {
    const modalId = 'dynamicLoadingModal';
    let modal = document.getElementById(modalId);
    
    if (!modal) {
      const modalHTML = `
        <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true" 
             data-bs-backdrop="static" data-bs-keyboard="false">
          <div class="modal-dialog modal-dialog-centered modal-sm">
            <div class="modal-content border-0 shadow">
              <div class="modal-body text-center py-4">
                <div class="spinner-border text-primary mb-3" role="status">
                  <span class="visually-hidden">Загрузка...</span>
                </div>
                <p class="mb-0 fw-semibold" id="loadingMessage">${message}</p>
              </div>
            </div>
          </div>
        </div>
      `;
      
      document.body.insertAdjacentHTML('beforeend', modalHTML);
      modal = document.getElementById(modalId);
    } else {
      document.getElementById('loadingMessage').textContent = message;
    }
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
    
    return bootstrapModal;
  },
  
  // Скрыть модальное окно загрузки
  hideLoadingModal: function() {
    const modal = document.getElementById('dynamicLoadingModal');
    if (modal) {
      const bootstrapModal = bootstrap.Modal.getInstance(modal);
      if (bootstrapModal) {
        bootstrapModal.hide();
      }
    }
  }
};

// Инициализация всех Bootstrap 5.3 компонентов при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
  // Инициализация tooltips
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
  // Инициализация popovers
  const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });
  
  // Автоматическое закрытие алертов
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function(alert) {
    // Автоматически закрываем через 10 секунд, если не указано иное
    const autoClose = alert.getAttribute('data-auto-close');
    if (autoClose !== 'false') {
      const delay = parseInt(autoClose) || 10000;
      setTimeout(function() {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
      }, delay);
    }
  });
});
