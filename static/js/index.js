document.addEventListener("DOMContentLoaded", () => {
    // ===================================
    // НОМЕР ДЕЛА ПО ДАТЕ (МОСКВА)
    // ===================================
    const caseNo = document.getElementById('caseNo');
    if (caseNo) {
        try {
            const msk = new Date(new Date().toLocaleString('en-US', { timeZone: 'Europe/Moscow' }));
            const y = msk.getFullYear();
            const mm = String(msk.getMonth() + 1).padStart(2, '0');
            const dd = String(msk.getDate()).padStart(2, '0');
            caseNo.textContent = `дело № ${y}-${mm}${dd}`;
        } catch (e) {
            // leave the server-rendered fallback
        }
    }

    // ===================================
    // АНИМАЦИЯ СЧЁТЧИКОВ СТАТИСТИКИ
    // ===================================
    const counters = document.querySelectorAll('.stat-value');

    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counter = entry.target;
                const target = parseInt(counter.dataset.target);
                const suffix = counter.dataset.suffix || '';
                const duration = 2000;
                const step = target / (duration / 16);
                let current = 0;

                const updateCounter = () => {
                    current += step;
                    if (current < target) {
                        counter.textContent = Math.floor(current).toLocaleString() + suffix;
                        requestAnimationFrame(updateCounter);
                    } else {
                        counter.textContent = target.toLocaleString() + suffix;
                    }
                };

                updateCounter();
                counterObserver.unobserve(counter);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => {
        if (counter.dataset.target) counterObserver.observe(counter);
    });

    // ===================================
    // FAQ АККОРДЕОН
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
    // ПРОВЕРКА URL С АВТОРИЗАЦИЕЙ
    // ===================================
    const checkerForm = document.getElementById("checkerForm");
    const urlInput = document.getElementById("urlInput");
    const checkerResult = document.getElementById("checker-result");
    const checkStatus = document.getElementById("check-status");

    // 1. Проверяем, есть ли сохраненная ссылка после входа (из URL параметра)
    const urlParams = new URLSearchParams(window.location.search);
    const pendingUrlFromUrl = urlParams.get('check');
    if (pendingUrlFromUrl) {
        urlInput.value = decodeURIComponent(pendingUrlFromUrl);
        // Очищаем URL от параметра, чтобы он не мешал при обновлении страницы
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 2. Проверяем, есть ли сохраненная ссылка в sessionStorage (если редирект только что произошел)
    const pendingUrlFromStorage = sessionStorage.getItem("pending_url");
    if (pendingUrlFromStorage && !urlInput.value) {
        urlInput.value = pendingUrlFromStorage;
        sessionStorage.removeItem("pending_url");
    }

    // 3. Обновляем кнопки навигации в зависимости от авторизации
    const token = localStorage.getItem("access_token");
    const loginBtn = document.getElementById("loginBtn");
    const dashboardLink = document.getElementById("dashboardLink");

    if (token) {
        if (loginBtn) loginBtn.style.display = "none";
        if (dashboardLink) dashboardLink.style.display = "inline-flex";
    }

    // 4. Обработка отправки формы
    if (checkerForm) {
        checkerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const url = urlInput.value.trim();

            if (!url) return;

            // ПРОВЕРКА АВТОРИЗАЦИИ
            const currentToken = localStorage.getItem("access_token");
            if (!currentToken) {
                showStatus("Создайте аккаунт - это займёт меньше минуты, и вы получите 3 бесплатные проверки. Перенаправляем...", "warning");
                sessionStorage.setItem("pending_url", url); // Сохраняем ссылку

                setTimeout(() => {
                    window.location.href = `auth.html?mode=register&check=${encodeURIComponent(url)}`;
                }, 1500);
                return;
            }

            // ЕСЛИ АВТОРИЗОВАН - ПРОВЕРЯЕМ
            showStatus("Анализируем ссылку...", "loading");
            checkerResult.hidden = true;

            try {
                const response = await fetch("/api/check-url", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${currentToken}`
                    },
                    body: JSON.stringify({ url })
                });

                if (response.status === 401) {
                    localStorage.removeItem("access_token");
                    throw new Error("Сессия истекла. Пожалуйста, войдите снова.");
                }

                if (response.status === 429) {
                    const data = await response.json();
                    const detail = data.detail || {};
                    // 429 бывает двух видов: кончились проверки по тарифу или слишком часто жмут кнопку
                    if (detail.checks_limit !== undefined) {
                        renderLimitReached(detail);
                    } else {
                        showStatus(detail.message || "Слишком много проверок подряд. Подождите минуту.", "warning");
                    }
                    return;
                }

                if (response.status === 403) {
                    const data = await response.json();
                    if (data.detail && data.detail.code === "email_not_verified") {
                        showStatus(
                            "Сначала подтвердите почту - ссылка пришла в письме при регистрации. " +
                            '<a href="dashboard.html">Отправить письмо ещё раз</a>',
                            "warning"
                        );
                        return;
                    }
                    throw new Error("Нет доступа к проверке.");
                }

                if (!response.ok) {
                    throw new Error("Ошибка при проверке URL. Попробуйте ещё раз.");
                }

                const data = await response.json();
                displayResult(data, url);

            } catch (error) {
                showStatus(error.message, "error");
                if (error.message.includes("Сессия истекла")) {
                    setTimeout(() => {
                        window.location.href = "auth.html";
                    }, 1500);
                }
            }
        });
    }

    // ===================================
    // ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
    // ===================================

    const FREE_STARTER_LIMIT = 3;

    function showQuotaStatus(data) {
        const remaining = data.checks_remaining;

        // Пользователи Про/Бизнес - без лимита
        if (remaining === null || remaining === undefined || remaining >= 9999) {
            showStatus("Проверка завершена. Проверки без ограничений на вашем тарифе.", "success");
            return;
        }

        if (remaining <= 3) {
            showUpgradeOffer(remaining);
        } else {
            showStatus(`Проверка завершена. Осталось ${remaining} из ${FREE_STARTER_LIMIT} бесплатных проверок.`, "success");
        }
    }

    function showUpgradeOffer(remaining) {
        if (!checkStatus) return;
        checkStatus.className = "form-status is-warning";
        checkStatus.style.display = "block";
        checkStatus.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:space-between; gap:14px; flex-wrap:wrap;">
                <span>Осталось ${remaining} ${remaining === 1 ? 'проверка' : 'проверки'} из ${FREE_STARTER_LIMIT}.
                Проверки нужны чаще? На тарифе Про доступно 200 проверок в месяц.</span>
                <a href="checkout.html?plan=pro" class="btn btn-verm btn-sm">Перейти на Про</a>
            </div>
        `;
    }

    function renderLimitReached(detail) {
        const used = detail.checks_used ?? FREE_STARTER_LIMIT;
        const limit = detail.checks_limit ?? FREE_STARTER_LIMIT;
        showStatus(
            `Вы использовали все ${limit} бесплатные проверки (${used}/${limit}). ` +
            `Чтобы проверять ссылки дальше, выберите тариф - Базовая (20 проверок) или Про (200 проверок).`,
            "warning"
        );
        if (!checkerResult) return;
        checkerResult.className = "result-card result-danger";
        checkerResult.hidden = false;
        checkerResult.innerHTML = `
            <div class="result-head">
                <span class="stamp stamp-verm">лимит</span>
                <div style="flex:1; min-width:180px;">
                    <div class="result-verdict">Бесплатные проверки закончились</div>
                </div>
            </div>
            <ul class="result-details">
                <li>После регистрации доступны ${limit} бесплатные проверки - один раз на аккаунт.</li>
                <li>Чтобы проверять ссылки дальше, выберите тариф - отменить подписку можно в любой момент.</li>
            </ul>
            <p style="margin-top:16px;">
                <a href="checkout.html?plan=pro" class="btn btn-verm btn-sm">Перейти на тариф Про</a>
            </p>
        `;
    }

    function showStatus(message, type) {
        if (!checkStatus) return;
        checkStatus.className = "form-status" + (type ? " is-" + type : "");
        checkStatus.style.display = "block";
        checkStatus.innerHTML = message;
    }

    function displayResult(data, url) {
        const isPhish = data.is_phishing;
        const isWarn = !isPhish && data.risk_score > 0.5;
        const statusClass = isPhish ? "result-danger" : (isWarn ? "result-warning" : "result-safe");
        const stampClass = isPhish ? "stamp-verm" : (isWarn ? "stamp-amber" : "stamp-sage");
        const badge = isPhish ? "фишинг" : (isWarn ? "под вопросом" : "чисто");
        const title = isPhish ? "Высокий риск фишинга" : (isWarn ? "Есть на что посмотреть" : "Ссылка выглядит чистой");

        const detailsHtml = data.details && data.details.length > 0
            ? `<ul class="result-details">${data.details.map(d => `<li>${d}</li>`).join('')}</ul>`
            : '';

        checkerResult.className = `result-card ${statusClass}`;
        checkerResult.hidden = false;
        checkerResult.innerHTML = `
            <div class="result-head">
                <span class="stamp ${stampClass}">${badge}</span>
                <div style="flex: 1; min-width: 180px;">
                    <div class="result-verdict">${title}</div>
                    <div class="result-url">${url}</div>
                </div>
                <div class="result-score">${Math.round(data.risk_score * 100)}%</div>
            </div>
            ${detailsHtml}
            <div class="result-title" hidden>${title}</div>
        `;

        // Счётчик лимита - мягкий триггер к апгрейду, пока человек «в потоке»
        if (typeof data.checks_remaining === "number") {
            const remaining = data.checks_remaining;
            const limitNote = document.createElement("p");
            limitNote.style.cssText = "margin-top:14px; font-size:0.85rem; color:var(--text-muted);";
            if (remaining > 2) {
                limitNote.textContent = `Осталось проверок: ${remaining}.`;
            } else {
                limitNote.innerHTML =
                    `Осталось проверок: ${remaining}. ` +
                    `<a href="checkout.html?plan=pro" style="color:var(--accent-primary); font-weight:600;">Про - 200 проверок в месяц →</a>`;
            }
            checkerResult.appendChild(limitNote);
        }
    }
});
// ===================================
// ПЛАВНЫЙ ПЕРЕХОД К СЕКЦИИ ПРИ КЛИКЕ ПО ЯКОРЮ (межстраничный)
// Если ссылка ведёт на другую страницу с #якорем - после загрузки
// докручиваем до нужной секции мягко, а не «прыгаем»
// ===================================
(function smoothCrossPageAnchor() {
    const hash = window.location.hash;
    if (!hash || hash.length < 2) return;
    try {
        const target = document.querySelector(hash);
        if (!target) return;
        // мгновенно ставим в начало, затем подстраховка плавным скроллом
        requestAnimationFrame(() => {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    } catch (e) { /* невалидный селектор - игнорируем */ }
})();

// ===================================
// ЭФФЕКТ «СЦЕНЫ» В СЕТКЕ ТАРИФОВ
// Когда мышь входит в сетку - карточки под ней «загораются»,
// остальные приглушаются (CSS-правило .pricing-grid.has-hover)
// ===================================
(function pricingGridScene() {
    const grid = document.getElementById('pricingGrid');
    if (!grid || !grid.classList.contains('tilt-grid')) return; // 3D-наклон только для карточного варианта
    if (!window.matchMedia('(pointer: fine)').matches) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    grid.addEventListener('mouseenter', () => grid.classList.add('has-hover'));
    grid.addEventListener('mouseleave', () => grid.classList.remove('has-hover'));

    // Tilt: карточка слегка наклоняется вслед за курсором + тёплая подсветка
    grid.querySelectorAll('.pricing-card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const r = card.getBoundingClientRect();
            const px = (e.clientX - r.left) / r.width - 0.5;
            const py = (e.clientY - r.top) / r.height - 0.5;
            card.style.transform = `rotateX(${(-py * 4).toFixed(2)}deg) rotateY(${(px * 5).toFixed(2)}deg) translateY(-4px)`;
            card.style.setProperty('--card-mouse-x', ((e.clientX - r.left) / r.width * 100).toFixed(1) + '%');
            card.style.setProperty('--card-mouse-y', ((e.clientY - r.top) / r.height * 100).toFixed(1) + '%');
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });
})();

// ===================================
// ВЫБОР ТАРИФА КЛИКОМ
// Если тариф выбран - красная подсветка закрепляется за ним и не
// «переходит» при наведении/скролле. Пока выбор не сделан - красный
// следует за курсором (обычное hover-поведение).
// ===================================
(function pricingSelect() {
    const grid = document.getElementById('pricingGrid');
    if (!grid) return;

    const cards = grid.querySelectorAll('.pricing-card');

    grid.addEventListener('click', (e) => {
        // клик по кнопке/ссылке внутри карточки не засчитываем как выбор
        if (e.target.closest('a,button')) return;
        const card = e.target.closest('.pricing-card');
        if (!card) return;

        const wasSelected = card.classList.contains('selected');
        cards.forEach(c => c.classList.remove('selected'));

        if (wasSelected) {
            grid.classList.remove('has-selected');
        } else {
            card.classList.add('selected');
            grid.classList.add('has-selected');
        }
    });
})();

// ===================================
// ОТЗЫВЫ: слайдер страницами по 3, листание стрелками влево/вправо
// ===================================
(function reviewsSlider() {
    const pages = [
        document.getElementById('testimonialsTrack'),
        document.getElementById('testimonialsPage2')
    ].filter(Boolean);
    const prevBtn = document.getElementById('reviewsPrev');
    const nextBtn = document.getElementById('reviewsNext');
    const dotsWrap = document.getElementById('reviewsDots');
    if (pages.length < 2 || !prevBtn || !nextBtn) return;

    let current = 0;

    // точки-индикаторы
    if (dotsWrap) {
        dotsWrap.textContent = '';
        pages.forEach((_, i) => {
            const d = document.createElement('button');
            d.type = 'button';
            d.className = 't-dot' + (i === 0 ? ' t-dot-active' : '');
            d.setAttribute('aria-label', `Страница отзывов ${i + 1}`);
            d.addEventListener('click', () => go(i));
            dotsWrap.appendChild(d);
        });
    }

    function animateIn(page) {
        page.querySelectorAll('.testimonial-card').forEach((card, i) => {
            card.classList.remove('review-enter');
            void card.offsetWidth; // перезапуск анимации
            card.style.animationDelay = `${i * 90}ms`;
            card.classList.add('review-enter');
        });
    }

    function go(index) {
        current = (index + pages.length) % pages.length;
        pages.forEach((page, i) => {
            if (i === current) {
                page.hidden = false;
                animateIn(page);
            } else {
                page.hidden = true;
            }
        });
        if (dotsWrap) {
            dotsWrap.querySelectorAll('.t-dot').forEach((d, i) =>
                d.classList.toggle('t-dot-active', i === current));
        }
    }

    prevBtn.addEventListener('click', () => go(current - 1));
    nextBtn.addEventListener('click', () => go(current + 1));

    // свайп на мобильных
    let startX = null;
    const slider = document.querySelector('.reviews-slider');
    if (slider) {
        slider.addEventListener('touchstart', e => { startX = e.touches[0].clientX; }, { passive: true });
        slider.addEventListener('touchend', e => {
            if (startX === null) return;
            const dx = e.changedTouches[0].clientX - startX;
            if (Math.abs(dx) > 50) go(current + (dx < 0 ? 1 : -1));
            startX = null;
        }, { passive: true });
    }
})();
