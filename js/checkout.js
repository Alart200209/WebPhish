// ===================================
// ПЛАН ДАННЫЕ
// ===================================
const plans = {
    free: {
        name: 'Бесплатный',
        price: 0,
        description: 'Навсегда',
        icon: 'fa-gift',
        features: [
            '10 проверок в день',
            'Базовый анализ',
            'Веб-интерфейс',
            'Email-поддержка'
        ]
    },
    pro: {
        name: 'Тариф Про',
        price: 299,
        description: 'Месячная подписка',
        icon: 'fa-crown',
        features: [
            'Безлимитные проверки',
            'API доступ',
            'История проверок',
            'Приоритетная поддержка'
        ]
    },
    business: {
        name: 'Тариф Бизнес',
        price: 1990,
        description: 'Месячная подписка',
        icon: 'fa-building',
        features: [
            'Всё из тарифа Про',
            'Командный доступ',
            'White-label решение',
            'Персональный менеджер',
            'SLA 99.9%'
        ]
    }
};

// ===================================
// ПОЛУЧАЕМ ПЛАН ИЗ URL
// ===================================
const urlParams = new URLSearchParams(window.location.search);
const planKey = urlParams.get('plan') || 'pro';
const trial = urlParams.get('trial') === 'true';
const selectedPlan = plans[planKey] || plans.pro;

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
                'Content-Type': 'application/json'
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