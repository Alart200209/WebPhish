// ===================================
// ПЛАН ДАННЫЕ
// ===================================
const plans = {
    basic: {
        name: 'Базовая подписка',
        price: 299,
        description: 'Месяц · 20 проверок',
        icon: 'fa-leaf',
        features: [
            '20 проверок в месяц',
            'Полный разбор признаков фишинга',
            'История проверок в кабинете',
            'Приоритетная поддержка'
        ]
    },
    pro: {
        name: 'Подписка Про',
        price: 999,
        description: 'Месяц · 200 проверок',
        icon: 'fa-crown',
        features: [
            '200 проверок в месяц',
            'Всё из базовой подписки',
            'API-доступ',
            'Ранний доступ к новым моделям анализа'
        ]
    },
    corporate: {
        name: 'Корпоративная подписка',
        price: 1990,
        description: 'Месяц · без лимита проверок',
        icon: 'fa-building',
        features: [
            'Проверки без лимита',
            'Командный доступ и общие отчёты',
            'Интеграция с корпоративной почтой',
            'SLA 99.9% и персональный менеджер'
        ]
    }
};

// ===================================
// ПОЛУЧАЕМ ПЛАН ИЗ URL
// ===================================
const urlParams = new URLSearchParams(window.location.search);
// Старые ключи ссылок (personal/business) — маппим на новые тарифы
const PLAN_ALIASES = { personal: 'basic', business: 'corporate' };
const rawPlanKey = urlParams.get('plan') || 'basic';
const planKey = PLAN_ALIASES[rawPlanKey] || rawPlanKey;
const trial = urlParams.get('trial') === 'true' || urlParams.get('trial') === '1';

// ===================================
// АВТОРИЗАЦИЯ: оплата доступна только вошедшим пользователям.
// Без токена отправляем на вход с возвратом обратно на checkout.
// ===================================
const authToken = localStorage.getItem('access_token');
if (!authToken) {
    const back = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.replace(`auth.html?mode=login&redirect=${back}`);
}

// Бесплатный тариф не требует оплаты — сразу ведём на регистрацию
if (planKey === 'free') {
    const check = urlParams.get('check');
    window.location.replace('auth.html?mode=register' + (check ? `&check=${encodeURIComponent(check)}` : ''));
}

const selectedPlan = plans[planKey] || plans.basic;

// ===================================
// ОБНОВЛЯЕМ ИНФОРМАЦИЮ О ПЛАНЕ
// ===================================
document.getElementById('planName').textContent = selectedPlan.name;
document.getElementById('planDescription').textContent = selectedPlan.description;
document.getElementById('planIcon').innerHTML = `<i class="fas ${selectedPlan.icon}"></i>`;

const displayPrice = trial && selectedPlan.price > 0 ? 0 : selectedPlan.price;
document.getElementById('planPrice').textContent = `${selectedPlan.price} ₽`;
document.getElementById('totalPrice').textContent = `${displayPrice} ₽`;

const featuresList = document.getElementById('planFeatures');
featuresList.innerHTML = selectedPlan.features.map(feature =>
    `<li><i class="fas fa-check"></i> ${feature}</li>`
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
        trial: trial,
        paymentMethod: document.querySelector('input[name="paymentMethod"]:checked').value
    };

    // Валидация
    if (!formData.firstName || !formData.lastName || !formData.email) {
        showStatus('Заполните все обязательные поля', 'error');
        return;
    }

    // Блокируем кнопку
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Создаем платеж...';

    try {
        // Отправляем запрос на backend
        const response = await fetch('/api/payment/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                amount: displayPrice * 100, // Tinkoff принимает в копейках
                order_id: `phishdet_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                description: `Подписка ${selectedPlan.name}`,
                customer: {
                    name: `${formData.firstName} ${formData.lastName}`,
                    email: formData.email,
                    phone: formData.phone
                },
                plan: planKey,
                trial: trial,
                payment_method: formData.paymentMethod
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Ошибка создания платежа');
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
        submitBtn.innerHTML = '<i class="fas fa-lock"></i> Перейти к оплате';
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