// ===================================
// ПЛАН ДАННЫЕ
// ===================================
const plans = {
    basic: {
        name: 'Базовая подписка',
        price: 99,
        description: 'Месяц · 20 проверок',
        tag: 'СТАРТ',
        features: [
            '20 проверок в месяц',
            'Разбор адреса нашей моделью, с причинами',
            'История проверок в кабинете',
            'Приоритетная поддержка'
        ]
    },
    pro: {
        name: 'Подписка Про',
        price: 299,
        description: 'Месяц · 200 проверок',
        tag: 'ПРО',
        features: [
            '200 проверок в месяц',
            'Всё из базовой подписки',
            'API-доступ',
            'Ранний доступ к новым моделям анализа'
        ]
    },
    corporate: {
        name: 'Корпоративная подписка',
        price: 4990,
        description: 'Месяц · без лимита проверок',
        tag: 'КОРП',
        features: [
            'Проверки без лимита',
            'Командный доступ и общие отчёты',
            'Интеграция с корпоративной почтой',
            'SLA 99,9 % и персональный менеджер'
        ]
    }
};

// ===================================
// ПОЛУЧАЕМ ПЛАН ИЗ URL
// ===================================
const urlParams = new URLSearchParams(window.location.search);
// Старые ключи ссылок (personal/business) - маппим на новые тарифы
const PLAN_ALIASES = { personal: 'basic', business: 'corporate' };
const rawPlanKey = urlParams.get('plan') || 'basic';
const aliasedPlanKey = PLAN_ALIASES[rawPlanKey] || rawPlanKey;
const planKey = aliasedPlanKey in plans ? aliasedPlanKey : 'basic';

// ===================================
// АВТОРИЗАЦИЯ: оплата доступна только вошедшим пользователям.
// Без токена отправляем на вход с возвратом обратно на checkout.
// ===================================
const authToken = localStorage.getItem('access_token');
if (!authToken) {
    const back = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`auth.html?mode=login&redirect=${back}`);
}

const selectedPlan = plans[planKey];

// ===================================
// ОБНОВЛЯЕМ ИНФОРМАЦИЮ О ПЛАНЕ
// ===================================
document.getElementById('planName').textContent = selectedPlan.name;
document.getElementById('planDescription').textContent = selectedPlan.description;
document.getElementById('planIcon').textContent = selectedPlan.tag;

const displayPrice = selectedPlan.price;
document.getElementById('planPrice').textContent = `${selectedPlan.price} ₽`;
document.getElementById('totalPrice').textContent = `${displayPrice} ₽`;

const featuresList = document.getElementById('planFeatures');
featuresList.innerHTML = selectedPlan.features.map(feature =>
    `<li>${feature}</li>`
).join('');

// ===================================
// ФОРМАТИРОВАНИЕ ТЕЛЕФОНА
// ===================================
const phoneInput = document.getElementById('phone');
phoneInput.addEventListener('input', (e) => {
    let value = e.target.value.replace(/\D/g, '');

    if (value.startsWith('8')) {
        value = '7' + value.slice(1);
    }

    if (value.length > 0 && !value.startsWith('7')) {
        value = '7' + value;
    }

    let formatted = '';
    if (value.length > 0) formatted = '+' + value.slice(0, 1);
    if (value.length > 1) formatted += ' (' + value.slice(1, 4);
    if (value.length > 4) formatted += ') ' + value.slice(4, 7);
    if (value.length > 7) formatted += '-' + value.slice(7, 9);
    if (value.length > 9) formatted += '-' + value.slice(9, 11);

    e.target.value = formatted;
});

// ===================================
// ОБРАБОТКА ФОРМЫ
// ===================================
const paymentForm = document.getElementById('paymentForm');
const submitBtn = document.getElementById('submitBtn');
const formStatus = document.getElementById('formStatus');
const successModal = document.getElementById('successModal');
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');
const redirectToPayment = document.getElementById('redirectToPayment');

paymentForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Собираем данные
    const formData = {
        firstName: document.getElementById('firstName').value.trim(),
        lastName: document.getElementById('lastName').value.trim(),
        email: document.getElementById('email').value.trim(),
        phone: document.getElementById('phone').value.trim(),
        plan: planKey,
        paymentMethod: document.querySelector('input[name="paymentMethod"]:checked').value
    };

    // Валидация
    if (!formData.firstName || !formData.lastName || !formData.email) {
        showStatus('Заполните все обязательные поля', 'error');
        return;
    }

    // Блокируем кнопку
    submitBtn.disabled = true;
    submitBtn.textContent = 'Создаём платёж…';

    try {
        // Отправляем запрос на backend
        const response = await fetch('/api/payment/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                amount: displayPrice * 100, // в копейках, сервер сверяет с ценой тарифа
                description: `Подписка ${selectedPlan.name}`,
                customer: {
                    name: `${formData.firstName} ${formData.lastName}`,
                    email: formData.email,
                    phone: formData.phone
                },
                plan: planKey,
                payment_method: formData.paymentMethod
            })
        });

        if (response.status === 401) {
            localStorage.removeItem('access_token');
            const back = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.replace(`auth.html?mode=login&expired=1&redirect=${back}`);
            return;
        }

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            if (data.detail && data.detail.code === 'email_not_verified') {
                throw new Error('Сначала подтвердите почту - ссылка пришла в письме при регистрации. Отправить письмо ещё раз можно в личном кабинете.');
            }
            throw new Error(window.PhishDetForms.errorText(data, 'Ошибка создания платежа'));
        }

        if (data.payment_url) {
            // Показываем модальное окно с кнопкой перехода
            redirectToPayment.href = data.payment_url;
            successModal.classList.add('active');
        } else {
            throw new Error('Не получена ссылка на оплату');
        }

    } catch (error) {
        console.error('Payment error:', error);
        errorMessage.textContent = error.message || 'Не удалось создать платеж. Попробуйте позже.';
        errorModal.classList.add('active');

        // Восстанавливаем кнопку
        submitBtn.disabled = false;
        submitBtn.textContent = 'Перейти к оплате';
    }
});

function showStatus(message, type) {
    formStatus.textContent = message;
    formStatus.className = `form-status show ${type}`;

    setTimeout(() => {
        formStatus.classList.remove('show');
    }, 5000);
}

// Закрытие модальных окон
successModal.addEventListener('click', (e) => {
    if (e.target === successModal) {
        successModal.classList.remove('active');
    }
});

errorModal.addEventListener('click', (e) => {
    if (e.target === errorModal) {
        errorModal.classList.remove('active');
    }
});