// Переключение между формами входа и регистрации
const tabs = document.querySelectorAll('.auth-tab');
const forms = document.querySelectorAll('.auth-form');

// Открываем нужную вкладку по ?mode=register (ссылки с лендинга и цен)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('mode') === 'register') {
    const registerTab = document.querySelector('.auth-tab[data-tab="register"]');
    if (registerTab) registerTab.click();
}

tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;

        // Убираем активный класс со всех вкладок
        tabs.forEach(t => t.classList.remove('active'));
        forms.forEach(f => f.classList.remove('active'));

        // Добавляем активный класс к выбранной вкладке
        tab.classList.add('active');
        document.getElementById(`${targetTab}Form`).classList.add('active');
    });
});

// Обработка входа
const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;

    loginStatus.classList.remove('show', 'error', 'success');

    try {
        // Отправляем запрос на вход
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const response = await fetch('/api/auth/login', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Ошибка входа');
        }

        // Сохраняем токен
        localStorage.setItem('access_token', data.access_token);

        // Показываем успех
        loginStatus.textContent = 'Успешный вход! Перенаправляем...';
        loginStatus.classList.add('show', 'success');

        // Если пришли проверять ссылку — возвращаем на главную сразу с ней
        const check = urlParams.get('check') || sessionStorage.getItem('pending_url');
        const pendingUrl = check ? encodeURIComponent(check) : '';
        sessionStorage.removeItem('pending_url');

        setTimeout(() => {
            window.location.href = 'index.html' + (pendingUrl ? `?check=${pendingUrl}` : '');
        }, 1000);

    } catch (error) {
        loginStatus.textContent = error.message;
        loginStatus.classList.add('show', 'error');
    }
});

// Обработка регистрации
const registerForm = document.getElementById('registerForm');
const registerStatus = document.getElementById('registerStatus');

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;
    const passwordConfirm = document.getElementById('registerPasswordConfirm').value;

    registerStatus.classList.remove('show', 'error', 'success');

    // Проверка совпадения паролей
    if (password !== passwordConfirm) {
        registerStatus.textContent = 'Пароли не совпадают';
        registerStatus.classList.add('show', 'error');
        return;
    }

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Ошибка регистрации');
        }

        // Показываем успех
        registerStatus.textContent = 'Аккаунт создан! Теперь вы можете войти.';
        registerStatus.classList.add('show', 'success');

        // Очищаем форму
        registerForm.reset();

        // Переключаемся на вкладку входа через 2 секунды
        setTimeout(() => {
            tabs[0].click();
        }, 2000);

    } catch (error) {
        registerStatus.textContent = error.message;
        registerStatus.classList.add('show', 'error');
    }
});

// Проверка, не авторизован ли уже пользователь
const token = localStorage.getItem('access_token');
if (token) {
    // Можно автоматически перенаправить на главную или в кабинет
    // window.location.href = 'dashboard.html';
}