// ===================================
// COUNTER ANIMATION
// ===================================
const counters = document.querySelectorAll('.stat-value');

const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const counter = entry.target;
            const target = parseInt(counter.dataset.target);
            const duration = 2000;
            const step = target / (duration / 16);
            let current = 0;

            const updateCounter = () => {
                current += step;
                if (current < target) {
                    counter.textContent = Math.floor(current).toLocaleString();
                    requestAnimationFrame(updateCounter);
                } else {
                    counter.textContent = target.toLocaleString();
                }
            };

            updateCounter();
            counterObserver.unobserve(counter);
        }
    });
}, { threshold: 0.5 });

counters.forEach(counter => counterObserver.observe(counter));

// ===================================
// FAQ ACCORDION
// ===================================
const faqItems = document.querySelectorAll('.faq-item');

faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');

    question.addEventListener('click', () => {
        const isActive = item.classList.contains('active');

        faqItems.forEach(i => i.classList.remove('active'));

        if (!isActive) {
            item.classList.add('active');
        }
    });
});

// ===================================
// URL CHECKER
// ===================================
const checkerForm = document.getElementById('checkerForm');
const urlInput = document.getElementById('urlInput');
const checkerResult = document.getElementById('checkerResult');

if (checkerForm) {
    checkerForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = urlInput.value.trim();

        if (!url) return;

        // Показываем загрузку
        checkerResult.classList.remove('show');
        checkerResult.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <i class="fas fa-spinner fa-spin" style="font-size: 2rem; color: var(--accent-primary);"></i>
                <p style="margin-top: 16px; color: var(--text-secondary);">Анализируем ссылку...</p>
            </div>
        `;
        checkerResult.classList.add('show');

        // Имитация проверки (замените на реальный API)
        setTimeout(() => {
            const result = analyzeUrl(url);
            displayResult(result, url);
        }, 1500);
    });
}

function analyzeUrl(url) {
    const urlLower = url.toLowerCase();

    const suspiciousKeywords = ['login', 'signin', 'verify', 'secure', 'account', 'update', 'bank', 'password'];
    const hasSuspiciousKeywords = suspiciousKeywords.some(keyword => urlLower.includes(keyword));

    const hasIP = /\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/.test(url);
    const hasAt = url.includes('@');
    const isLong = url.length > 75;
    const hasManyDots = (url.match(/\./g) || []).length > 4;
    const hasManyHyphens = (url.match(/-/g) || []).length >= 3;

    let score = 0;
    const details = [];

    if (hasSuspiciousKeywords) {
        score += 30;
        details.push('Обнаружены подозрительные ключевые слова');
    }

    if (hasIP) {
        score += 40;
        details.push('Использован IP-адрес вместо домена');
    }

    if (hasAt) {
        score += 25;
        details.push('Символ @ в URL может маскировать адрес');
    }

    if (isLong) {
        score += 10;
        details.push('Необычно длинный URL');
    }

    if (hasManyDots) {
        score += 15;
        details.push('Много поддоменов');
    }

    if (hasManyHyphens) {
        score += 10;
        details.push('Много дефисов в домене');
    }

    if (!url.startsWith('https://')) {
        score += 15;
        details.push('Не используется HTTPS');
    }

    score = Math.min(score, 100);

    let status, icon, title;

    if (score >= 70) {
        status = 'danger';
        icon = 'fa-exclamation-triangle';
        title = 'Высокий риск фишинга';
    } else if (score >= 40) {
        status = 'warning';
        icon = 'fa-exclamation-circle';
        title = 'Подозрительная ссылка';
    } else {
        status = 'safe';
        icon = 'fa-check-circle';
        title = 'Ссылка безопасна';
    }

    return { score, status, icon, title, details };
}

function displayResult(result, url) {
    let detailsHTML = '';
    if (result.details.length > 0) {
        detailsHTML = `
            <div class="result-details">
                ${result.details.map(detail => `
                    <div class="result-detail">
                        <i class="fas fa-info-circle"></i>
                        <span>${detail}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    checkerResult.innerHTML = `
        <div class="result-header">
            <div class="result-icon ${result.status}">
                <i class="fas ${result.icon}"></i>
            </div>
            <div>
                <div class="result-title">${result.title}</div>
                <div class="result-url">${url}</div>
            </div>
        </div>
        ${detailsHTML}
    `;

    checkerResult.classList.add('show');
}