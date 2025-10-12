// Кастомный JavaScript для админки Django

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация tooltips для статусов в админке
    const statusElements = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    statusElements.forEach(function(element) {
        // Простая реализация tooltip без Bootstrap
        element.addEventListener('mouseenter', function() {
            const title = this.getAttribute('title') || this.getAttribute('data-original-title');
            if (title) {
                const tooltip = document.createElement('div');
                tooltip.className = 'admin-tooltip';
                tooltip.textContent = title;
                tooltip.style.cssText = `
                    position: absolute;
                    background: #333;
                    color: white;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                    z-index: 1000;
                    pointer-events: none;
                `;
                document.body.appendChild(tooltip);
                
                const rect = this.getBoundingClientRect();
                tooltip.style.left = rect.left + 'px';
                tooltip.style.top = (rect.top - tooltip.offsetHeight - 5) + 'px';
                
                this._tooltip = tooltip;
            }
        });
        
        element.addEventListener('mouseleave', function() {
            if (this._tooltip) {
                document.body.removeChild(this._tooltip);
                this._tooltip = null;
            }
        });
    });
});