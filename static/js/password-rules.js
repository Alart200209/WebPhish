// ===================================
// Общие помощники для форм с паролем.
// Требования повторяют серверные (api/auth.py: validate_password) -
// здесь они только чтобы показать ошибку сразу, решает всё равно сервер.
// ===================================
(function () {
    const COMMON_PASSWORDS = new Set([
        '12345678', '123456789', '1234567890', 'password', 'password1', 'password123',
        'qwerty123', 'qwertyuiop', '1q2w3e4r', '1q2w3e4r5t', 'qwerty12', '11111111',
        '00000000', '88888888', 'iloveyou', 'abc12345', 'admin123', 'admin12345',
        'passw0rd', '123qwe123', 'zaq12wsx', '1qaz2wsx', 'qazwsx123', 'phishdet1'
    ]);

    // Возвращает текст ошибки или null, если пароль подходит
    function checkPassword(password, email) {
        if (password.length < 8) return 'Пароль должен быть не короче 8 символов';
        if (new TextEncoder().encode(password).length > 72) {
            return 'Пароль слишком длинный: максимум 72 байта (около 36 символов кириллицей)';
        }
        if (password !== password.trim()) return 'Пароль не должен начинаться или заканчиваться пробелом';
        if (!/[A-Za-zА-Яа-яЁё]/.test(password) || !/\d/.test(password)) {
            return 'Пароль должен содержать хотя бы одну букву и одну цифру';
        }
        if (COMMON_PASSWORDS.has(password.toLowerCase())) {
            return 'Этот пароль слишком распространён - придумайте другой';
        }
        if (email) {
            const lowered = password.toLowerCase();
            const localPart = email.split('@')[0].toLowerCase();
            if (lowered === email.toLowerCase() || (localPart.length >= 4 && lowered.includes(localPart))) {
                return 'Пароль не должен повторять адрес почты';
            }
        }
        return null;
    }

    // Достаёт понятный текст из ответа API: detail бывает строкой,
    // объектом {message} (лимиты, 429) или списком ошибок валидации (422)
    function errorText(data, fallback) {
        const detail = data && data.detail;
        if (typeof detail === 'string') return detail;
        if (detail && typeof detail.message === 'string') return detail.message;
        if (Array.isArray(detail) && detail.length) {
            return String(detail[0].msg || fallback).replace(/^Value error, /, '');
        }
        return fallback;
    }

    window.PhishDetForms = { checkPassword, errorText };
})();
