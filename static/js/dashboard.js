const { checkPassword, errorText } = window.PhishDetForms;

// Проверка авторизации
let token = localStorage.getItem('access_token');

if (!token) {
    // Если нет токена, перенаправляем на страницу входа
    window.location.href = 'auth.html';
}

// Тарифов три. «free» - не тариф, а стартовый пакет из 3 проверок после регистрации.
const PLAN_NAMES = {
    basic: 'Базовая',
    pro: 'Про',
    corporate: 'Корпоративная'
};

// Ответ 401 - токен истёк или пароль сменили на другом устройстве
class SessionExpiredError extends Error {}

function sessionExpired() {
    localStorage.removeItem('access_token');
    window.location.href = 'auth.html?expired=1';
}

async function apiGet(url) {
    const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.status === 401) throw new SessionExpiredError();
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorText(data, 'Не удалось загрузить данные'));
    return data;
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[ch]);
}

// Сервер отдаёт время в UTC, иногда без зоны - добавляем её явно
function parseServerDate(iso) {
    return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z');
}

function setStatus(el, message, type) {
    el.classList.remove('show', 'error', 'success');
    if (!message) return;
    el.textContent = message;
    el.classList.add('show', type);
}

// Выход
const logoutBtn = document.getElementById('logoutBtn');
logoutBtn.addEventListener('click', () => {
    localStorage.removeItem('access_token');
    window.location.href = 'index.html';
});

// Загрузка данных пользователя
async function loadUserData() {
    try {
        const userData = await apiGet('/api/auth/me');

        // Отображаем данные
        document.getElementById('userEmail').textContent = userData.email;
        const isSubscribed = userData.subscription_plan in PLAN_NAMES;
        document.getElementById('userPlan').textContent =
            isSubscribed ? PLAN_NAMES[userData.subscription_plan] : 'без подписки';
        document.getElementById('checksLabel').textContent =
            isSubscribed ? 'проверок за месяц' : 'бесплатных проверок';

        // Срок действия подписки
        const expiresRow = document.getElementById('planExpiresRow');
        if (isSubscribed && userData.subscription_expires_at) {
            document.getElementById('planExpires').textContent =
                parseServerDate(userData.subscription_expires_at).toLocaleDateString('ru-RU', {
                    day: 'numeric', month: 'long', year: 'numeric'
                });
            expiresRow.hidden = false;
        } else {
            expiresRow.hidden = true;
        }

        // Почта не подтверждена - показываем плашку с повторной отправкой письма
        if (!userData.email_verified) {
            document.getElementById('verifyEmail').textContent = userData.email;
            document.getElementById('verifyBanner').hidden = false;
        }

        // Администратору показываем ссылку на модерацию отзывов
        const adminLink = document.getElementById('adminLink');
        if (adminLink && userData.is_admin) {
            adminLink.hidden = false;
        }

        // Получаем лимит проверок
        const limitData = await apiGet('/api/auth/check-limit');

        document.getElementById('checksUsed').textContent = limitData.checks_used;
        document.getElementById('checksLimit').textContent =
            limitData.checks_limit === 'unlimited' ? '∞' : limitData.checks_limit;

        // Загружаем историю проверок
        await loadChecksHistory();

    } catch (error) {
        if (error instanceof SessionExpiredError) {
            sessionExpired();
            return;
        }
        console.error('Ошибка загрузки данных:', error);
    }
}

// Загрузка истории проверок
async function loadChecksHistory() {
    const checks = await apiGet('/api/checks/history');

    const checksList = document.getElementById('checksList');

    if (checks.length === 0) {
        checksList.innerHTML = `
            <div class="empty-state">
                <p class="hand">тут пока пусто</p>
                <p>Вы ещё ничего не проверяли. Начните с той самой подозрительной ссылки.</p>
                <a href="index.html#checker" class="btn btn-verm">Проверить ссылку</a>
            </div>
        `;
        return;
    }

    // Подсчитываем угрозы
    const threats = checks.filter(c => c.is_phishing).length;
    document.getElementById('threatsDetected').textContent = threats;

    // Последняя проверка
    const lastCheck = parseServerDate(checks[0].created_at);
    const diffMins = Math.floor((new Date() - lastCheck) / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    let timeText;
    if (diffMins < 1) {
        timeText = 'Только что';
    } else if (diffMins < 60) {
        timeText = `${diffMins} мин. назад`;
    } else if (diffHours < 24) {
        timeText = `${diffHours} ч. назад`;
    } else {
        timeText = `${diffDays} дн. назад`;
    }

    document.getElementById('lastCheck').textContent = timeText;

    // Отображаем список проверок. URL - то, что ввёл пользователь, поэтому экранируем.
    checksList.innerHTML = checks.map(check => {
        const statusClass = check.is_phishing ? 'danger' :
                           check.risk_score > 0.5 ? 'warning' : 'safe';
        const statusText = check.is_phishing ? 'фишинг' :
                          check.risk_score > 0.5 ? 'подозрительно' : 'безопасно';

        const dateStr = parseServerDate(check.created_at).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit'
        });

        return `
            <div class="check-item">
                <div class="check-status ${statusClass}">${statusText}</div>
                <div class="check-info">
                    <div class="check-url">${escapeHtml(check.url)}</div>
                    <div class="check-meta">
                        <span>${dateStr}</span>
                    </div>
                </div>
                <div class="check-score">${Math.round(check.risk_score * 100)}%</div>
            </div>
        `;
    }).join('');
}

// Повторная отправка письма для подтверждения почты
const resendVerifyBtn = document.getElementById('resendVerifyBtn');
const verifyStatus = document.getElementById('verifyStatus');

resendVerifyBtn.addEventListener('click', async () => {
    resendVerifyBtn.disabled = true;
    setStatus(verifyStatus, null);
    try {
        const response = await fetch('/api/auth/resend-verification', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.status === 401) return sessionExpired();
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorText(data, 'Не удалось отправить письмо'));
        setStatus(verifyStatus, data.message, 'success');
    } catch (error) {
        setStatus(verifyStatus, error.message, 'error');
    } finally {
        resendVerifyBtn.disabled = false;
    }
});

// Смена пароля
const changePasswordForm = document.getElementById('changePasswordForm');
const changePasswordStatus = document.getElementById('changePasswordStatus');

changePasswordForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirm = document.getElementById('newPasswordConfirm').value;
    const email = document.getElementById('userEmail').textContent;

    setStatus(changePasswordStatus, null);

    const passwordError = checkPassword(newPassword, email);
    if (passwordError) return setStatus(changePasswordStatus, passwordError, 'error');
    if (newPassword !== confirm) return setStatus(changePasswordStatus, 'Пароли не совпадают', 'error');
    if (newPassword === currentPassword) {
        return setStatus(changePasswordStatus, 'Новый пароль совпадает с текущим', 'error');
    }

    const submit = changePasswordForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
        });
        if (response.status === 401) return sessionExpired();
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(errorText(data, 'Не удалось сменить пароль'));

        // Старые токены больше не действуют - сохраняем новый
        token = data.access_token;
        localStorage.setItem('access_token', token);
        changePasswordForm.reset();
        setStatus(changePasswordStatus, 'Пароль изменён. Входы на других устройствах завершены.', 'success');
    } catch (error) {
        setStatus(changePasswordStatus, error.message, 'error');
    } finally {
        submit.disabled = false;
    }
});

// Загружаем данные при загрузке страницы
loadUserData();
