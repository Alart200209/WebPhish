// Проверка авторизации
const token = localStorage.getItem('access_token');

if (!token) {
    // Если нет токена, перенаправляем на страницу входа
    window.location.href = 'auth.html';
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
        // Получаем информацию о пользователе
        const userResponse = await fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!userResponse.ok) {
            throw new Error('Не удалось загрузить данные пользователя');
        }

        const userData = await userResponse.json();

        // Отображаем данные
        document.getElementById('userEmail').textContent = userData.email;
        document.getElementById('userPlan').textContent =
            userData.subscription_plan === 'free' ? 'Бесплатный' :
            userData.subscription_plan === 'pro' ? 'Про' : 'Бизнес';

        // Администратору показываем ссылку на модерацию отзывов
        const adminLink = document.getElementById('adminLink');
        if (adminLink && userData.is_admin) {
            adminLink.hidden = false;
        }

        // Получаем лимит проверок
        const limitResponse = await fetch('/api/auth/check-limit', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        const limitData = await limitResponse.json();

        document.getElementById('checksUsed').textContent = limitData.checks_used;
        document.getElementById('checksLimit').textContent =
            limitData.checks_limit === 'unlimited' ? '∞' : limitData.checks_limit;

        // Загружаем историю проверок
        loadChecksHistory();

    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        // Если токен невалиден, перенаправляем на вход
        if (error.message.includes('401')) {
            localStorage.removeItem('access_token');
            window.location.href = 'auth.html';
        }
    }
}

// Загрузка истории проверок
async function loadChecksHistory() {
    try {
        const response = await fetch('/api/checks/history', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error('Не удалось загрузить историю');
        }

        const checks = await response.json();

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
        if (checks.length > 0) {
            const lastCheck = new Date(checks[0].created_at);
            const now = new Date();
            const diffMs = now - lastCheck;
            const diffMins = Math.floor(diffMs / 60000);
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
        }

        // Отображаем список проверок
        checksList.innerHTML = checks.map(check => {
            const statusClass = check.is_phishing ? 'danger' :
                               check.risk_score > 0.5 ? 'warning' : 'safe';
            const statusText = check.is_phishing ? 'фишинг' :
                              check.risk_score > 0.5 ? 'подозрительно' : 'безопасно';

            const date = new Date(check.created_at);
            const dateStr = date.toLocaleDateString('ru-RU', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
            });

            return `
                <div class="check-item">
                    <div class="check-status ${statusClass}">${statusText}</div>
                    <div class="check-info">
                        <div class="check-url">${check.url}</div>
                        <div class="check-meta">
                            <span>${dateStr}</span>
                        </div>
                    </div>
                    <div class="check-score">${Math.round(check.risk_score * 100)}%</div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Ошибка загрузки истории:', error);
    }
}

// Загружаем данные при загрузке страницы
loadUserData();