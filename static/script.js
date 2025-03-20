// Анимация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('.container').classList.add('fade-in');
});

// Обработчик для кнопки
document.querySelectorAll('.button').forEach(button => {
    button.addEventListener('click', () => {
        alert('🎉 Кнопка работает!');
    });
});

// Динамическое изменение цвета карточек
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.backgroundColor = '#f0f0f0';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.backgroundColor = 'white';
    });
});
