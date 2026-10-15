// Сброс пароля по ссылке из письма: reset-password.html?token=...
(function () {
    const { checkPassword, errorText } = window.PhishDetForms;
    const form = document.getElementById('resetForm');
    const status = document.getElementById('resetStatus');
    const submit = form.querySelector('button[type="submit"]');

    const token = new URLSearchParams(window.location.search).get('token');
    // Убираем токен из адресной строки, чтобы он не остался в истории браузера
    window.history.replaceState({}, document.title, window.location.pathname);

    function setStatus(message, type) {
        status.textContent = message;
        status.className = `auth-status show ${type}`;
    }

    if (!token) {
        setStatus('В ссылке нет кода сброса. Откройте её из письма целиком или запросите сброс ещё раз на странице входа.', 'error');
        submit.disabled = true;
        return;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('newPassword').value;
        const confirm = document.getElementById('newPasswordConfirm').value;

        const passwordError = checkPassword(password);
        if (passwordError) return setStatus(passwordError, 'error');
        if (password !== confirm) return setStatus('Пароли не совпадают', 'error');

        submit.disabled = true;
        try {
            const response = await fetch('/api/auth/reset-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token, new_password: password })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorText(data, 'Не удалось сменить пароль'));

            // Старый токен в этом браузере тоже больше не действует
            localStorage.removeItem('access_token');
            setStatus('Пароль изменён. Перенаправляем ко входу…', 'success');
            setTimeout(() => { window.location.href = 'auth.html?reset=1'; }, 1500);
        } catch (error) {
            setStatus(error.message, 'error');
            submit.disabled = false;
        }
    });
})();
