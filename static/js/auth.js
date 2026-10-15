const { checkPassword, errorText } = window.PhishDetForms;

// Переключение между формами входа и регистрации
const tabs = document.querySelectorAll('.auth-tab');
const forms = document.querySelectorAll('.auth-form');

function showForm(name) {
    forms.forEach(f => f.classList.toggle('active', f.id === `${name}Form`));
    // Форма восстановления - не вкладка, при ней ни одна вкладка не подсвечена
    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
}

tabs.forEach(tab => {
    tab.addEventListener('click', () => showForm(tab.dataset.tab));
});

function setStatus(el, message, type) {
    el.classList.remove('show', 'error', 'success');
    if (!message) return;
    el.textContent = message;
    el.classList.add('show', type);
}

// Открываем нужную вкладку по ?mode=register (ссылки с лендинга и цен).
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('mode') === 'register') {
    showForm('register');
}

// Куда вернуть после входа: только относительный путь на этом же сайте,
// иначе ссылкой вида auth.html?redirect=https://evil.example можно увести пользователя
function safeRedirect(value) {
    if (!value) return null;
    if (!value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return null;
    return value;
}

// Обработка входа
const loginForm = document.getElementById('loginForm');
const loginStatus = document.getElementById('loginStatus');

if (urlParams.get('reset') === '1') {
    setStatus(loginStatus, 'Пароль изменён. Войдите с новым паролем.', 'success');
}
if (urlParams.get('expired') === '1') {
    setStatus(loginStatus, 'Сессия закончилась - войдите снова.', 'error');
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value;

    setStatus(loginStatus, null);

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
            throw new Error(errorText(data, 'Ошибка входа'));
        }

        // Сохраняем токен
        localStorage.setItem('access_token', data.access_token);

        setStatus(loginStatus, 'Успешный вход! Перенаправляем...', 'success');

        const redirect = safeRedirect(urlParams.get('redirect'));
        // Если пришли проверять ссылку - возвращаем на главную сразу с ней
        const check = urlParams.get('check') || sessionStorage.getItem('pending_url');
        const pendingUrl = check ? encodeURIComponent(check) : '';
        sessionStorage.removeItem('pending_url');

        setTimeout(() => {
            window.location.href = redirect || ('index.html' + (pendingUrl ? `?check=${pendingUrl}` : ''));
        }, 1000);

    } catch (error) {
        setStatus(loginStatus, error.message, 'error');
    }
});

// Восстановление пароля
const forgotForm = document.getElementById('forgotForm');
const forgotStatus = document.getElementById('forgotStatus');

document.getElementById('forgotLink').addEventListener('click', () => {
    document.getElementById('forgotEmail').value = document.getElementById('loginEmail').value.trim();
    setStatus(forgotStatus, null);
    showForm('forgot');
});
document.getElementById('backToLogin').addEventListener('click', () => showForm('login'));

forgotForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('forgotEmail').value.trim();
    const submit = forgotForm.querySelector('button[type="submit"]');

    setStatus(forgotStatus, null);
    submit.disabled = true;

    try {
        const response = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(errorText(data, 'Не удалось отправить письмо'));
        }

        setStatus(forgotStatus, data.message, 'success');
    } catch (error) {
        setStatus(forgotStatus, error.message, 'error');
    } finally {
        submit.disabled = false;
    }
});

// Обработка регистрации
const registerForm = document.getElementById('registerForm');
const registerStatus = document.getElementById('registerStatus');

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('registerEmail').value.trim();
    const password = document.getElementById('registerPassword').value;
    const passwordConfirm = document.getElementById('registerPasswordConfirm').value;

    setStatus(registerStatus, null);

    const passwordError = checkPassword(password, email);
    if (passwordError) {
        setStatus(registerStatus, passwordError, 'error');
        return;
    }

    // Проверка совпадения паролей
    if (password !== passwordConfirm) {
        setStatus(registerStatus, 'Пароли не совпадают', 'error');
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
            throw new Error(errorText(data, 'Ошибка регистрации'));
        }

        setStatus(
            registerStatus,
            `Аккаунт создан! Мы отправили письмо на ${data.email} - перейдите по ссылке из него, чтобы подтвердить почту. А пока можно войти.`,
            'success'
        );

        registerForm.reset();
        document.getElementById('loginEmail').value = data.email;

        // Переключаемся на вкладку входа, чтобы успели прочитать про письмо
        setTimeout(() => {
            showForm('login');
            setStatus(loginStatus, `Письмо для подтверждения ушло на ${data.email}. Введите пароль, чтобы войти.`, 'success');
        }, 4000);

    } catch (error) {
        setStatus(registerStatus, error.message, 'error');
    }
});
