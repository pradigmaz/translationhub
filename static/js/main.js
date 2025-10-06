// static/js/main.js

// Этот код будет выполнен, когда весь HTML-документ загрузится
document.addEventListener('DOMContentLoaded', () => {

    // Находим все элементы, которые нужно анимировать
    const featureItems = document.querySelectorAll('.feature-item');

    // Intersection Observer - это современный способ отслеживать,
    // виден ли элемент на экране. Он гораздо эффективнее, чем отслеживание скролла.
    const observer = new IntersectionObserver((entries) => {
        // entries - это массив элементов, за которыми мы следим
        entries.forEach(entry => {
            // isIntersecting - это свойство, которое становится true,
            // когда элемент появляется в видимой области экрана.
            if (entry.isIntersecting) {
                // Добавляем класс 'visible', который запускает CSS-анимацию
                entry.target.classList.add('visible');
            }
        });
    }, {
        // threshold: 0.1 означает, что анимация сработает,
        // когда будет видно хотя бы 10% элемента.
        threshold: 0.1
    });

    // Говорим "наблюдателю" следить за каждым из наших элементов
    featureItems.forEach(item => {
        observer.observe(item);
    });
});