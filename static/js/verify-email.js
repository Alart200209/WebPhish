// Подтверждение почты по ссылке из письма: verify-email.html?token=...
(function () {
    const { errorText } = window.PhishDetForms;
    const title = document.getElementById('verifyTitle');
    const text = document.getElementById('verifyText');
    const actions = document.getElementById('verifyActions');

    const token = new URLSearchParams(window.location.search).get('token');
    // Убираем токен из адресной строки, чтобы он не остался в истории браузера
    window.history.replaceState({}, document.title, window.location.pathname);

    const loggedIn = Boolean(localStorage.getItem('access_token'));

    function finish(heading, message, links) {
        title.textContent = heading;
        text.textContent = message;
        actions.innerHTML = links
            .map(([href, label, cls]) => `<a href="${href}" class="btn ${cls}">${label}</a>`)
            .join('');
        actions.hidden = false;
    }

    if (!token) {
        finish('Ссылка неполная', 'В ссылке нет кода подтверждения. Откройте её из письма целиком или запросите новое письмо в личном кабинете.',
            [[loggedIn ? 'dashboard.html' : 'auth.html', loggedIn ? 'В личный кабинет' : 'Войти', 'btn-verm']]);
        return;
    }

    fetch('/api/auth/verify-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
    })
        .then(async (response) => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorText(data, 'Не удалось подтвердить почту'));

            finish('Почта подтверждена', 'Готово - теперь можно проверять ссылки. После регистрации доступны 3 бесплатные проверки.',
                loggedIn
                    ? [['index.html#checker', 'Проверить ссылку', 'btn-verm'], ['dashboard.html', 'В личный кабинет', 'btn-ink']]
                    : [['auth.html', 'Войти', 'btn-verm']]);
        })
        .catch((error) => {
            finish('Не получилось', error.message,
                [[loggedIn ? 'dashboard.html' : 'auth.html', loggedIn ? 'Запросить новое письмо' : 'Войти', 'btn-verm']]);
        });
})();
