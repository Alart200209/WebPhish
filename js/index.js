document.addEventListener("DOMContentLoaded", () => {
    // ===================================
    // АНИМАЦИЯ СЧЁТЧИКОВ СТАТИСТИКИ
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
                showStatus("Создайте аккаунт — это займёт меньше минуты, и вы получите 10 бесплатных проверок в месяц. Перенаправляем...", "warning");
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
                    renderLimitReached(data.detail || {});
                    return;
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

    const FREE_MONTHLY_LIMIT = 10;

    function showQuotaStatus(data) {
        const remaining = data.checks_remaining;

        // Пользователи Про/Бизнес — без лимита
        if (remaining === null || remaining === undefined || remaining >= 9999) {
            showStatus("Проверка завершена. На вашем тарифе проверки без ограничений.", "success");
            return;
        }

        if (remaining <= 3) {
            showUpgradeOffer(remaining);
        } else {
            showStatus(`Проверка завершена. Осталось ${remaining} из ${FREE_MONTHLY_LIMIT} проверок в этом месяце.`, "success");
        }
    }

    function showUpgradeOffer(remaining) {
        if (!checkStatus) return;
        checkStatus.innerHTML = `
            <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;">
                <span>Осталось ${remaining} ${remaining === 1 ? 'проверка' : remaining < 5 ? 'проверки' : 'проверок'} из ${FREE_MONTHLY_LIMIT}.
                Проверки нужны чаще? Тариф Про — безлимит, первые 7 дней бесплатно.</span>
                <a href="checkout.html?plan=pro&trial=1" class="btn btn-primary" style="padding:8px 16px; min-height:38px; font-size:0.85rem;">Попробовать Про</a>
            </div>
        `;
        checkStatus.style.display = "block";
        checkStatus.style.padding = "12px";
        checkStatus.style.borderRadius = "12px";
        checkStatus.style.fontSize = "0.95rem";
        checkStatus.style.background = "rgba(245, 165, 36, 0.1)";
        checkStatus.style.border = "1px solid rgba(245, 165, 36, 0.35)";
        checkStatus.style.color = "var(--text-primary)";
    }

    function renderLimitReached(detail) {
        const used = detail.checks_used ?? FREE_MONTHLY_LIMIT;
        const limit = detail.checks_limit ?? FREE_MONTHLY_LIMIT;
        showStatus(
            `Вы использовали все ${limit} бесплатных проверок этого месяца (${used}/${limit}). ` +
            `Новые проверки будут доступны с начала следующего месяца или оформите тариф Про — безлимит с первыми 7 днями бесплатно.`,
            "warning"
        );
        if (!checkerResult) return;
        checkerResult.className = "result-card result-warning";
        checkerResult.hidden = false;
        checkerResult.style.cssText = "padding:20px; border-radius:var(--radius-md); margin-top:16px; border:1px solid rgba(168,118,12,0.35); border-left:3px solid var(--accent-warning); background:var(--bg-elevated); box-shadow:var(--shadow-sm);";
        checkerResult.innerHTML = `
            <div style="font-weight:700; font-size:1.1rem; margin-bottom:8px; color:var(--text-primary);">Лимит бесплатных проверок исчерпан</div>
            <p style="color:var(--text-secondary); font-size:0.95rem; margin-bottom:16px;">
                Бесплатный тариф включает ${limit} проверок в месяц. С тарифом Про проверки не ограничены,
                а первые 7 дней стоят 0 ₽ — отменить можно в любой момент.
            </p>
            <a href="checkout.html?plan=pro&trial=1" class="btn btn-primary btn-arrow">Попробовать Про 7 дней бесплатно</a>
            <div class="result-title" hidden>Лимит бесплатных проверок исчерпан</div>
        `;
    }

    function showStatus(message, type) {
        if (!checkStatus) return;
        checkStatus.innerHTML = message;
        checkStatus.style.display = "block";
        checkStatus.style.padding = "12px";
        checkStatus.style.borderRadius = "12px";
        checkStatus.style.fontSize = "0.95rem";

        if (type === "error") {
            checkStatus.style.background = "rgba(239, 68, 68, 0.1)";
            checkStatus.style.border = "1px solid rgba(239, 68, 68, 0.3)";
            checkStatus.style.color = "var(--accent-danger, #ef4444)";
        } else if (type === "warning") {
            checkStatus.style.background = "rgba(245, 158, 11, 0.1)";
            checkStatus.style.border = "1px solid rgba(245, 158, 11, 0.3)";
            checkStatus.style.color = "var(--accent-warning, #f59e0b)";
        } else if (type === "success") {
            checkStatus.style.background = "rgba(16, 185, 129, 0.1)";
            checkStatus.style.border = "1px solid rgba(16, 185, 129, 0.3)";
            checkStatus.style.color = "var(--accent-success, #10b981)";
        } else {
            checkStatus.style.background = "rgba(245, 165, 36, 0.1)";
            checkStatus.style.border = "1px solid rgba(245, 165, 36, 0.35)";
            checkStatus.style.color = "var(--accent-primary, #f5a524)";
        }
    }

    function displayResult(data, url) {
        const statusClass = data.is_phishing ? "result-danger" : (data.risk_score > 0.5 ? "result-warning" : "result-safe");
        const icon = data.is_phishing ? "fa-exclamation-triangle" : (data.risk_score > 0.5 ? "fa-exclamation-circle" : "fa-check-circle");
        const title = data.is_phishing ? "Высокий риск фишинга" : (data.risk_score > 0.5 ? "Требуется осторожность" : "Ссылка безопасна");

        const detailsHtml = data.details && data.details.length > 0
            ? `<ul style="margin-top: 12px; padding-left: 20px; color: var(--text-secondary); font-size: 0.9rem;">
                ${data.details.map(d => `<li style="margin-bottom: 4px;">${d}</li>`).join('')}
               </ul>`
            : '';

        const borderColor = statusClass === 'result-danger' ? 'rgba(239, 68, 68, 0.3)' :
                           (statusClass === 'result-warning' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(16, 185, 129, 0.3)');
        const bgColor = statusClass === 'result-danger' ? 'rgba(239, 68, 68, 0.1)' :
                       (statusClass === 'result-warning' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(16, 185, 129, 0.1)');
        const textColor = statusClass === 'result-danger' ? 'var(--accent-danger)' :
                         (statusClass === 'result-warning' ? 'var(--accent-warning)' : 'var(--accent-success)');

        checkerResult.className = `result-card ${statusClass}`;
        checkerResult.hidden = false;
        checkerResult.style.padding = "20px";
        checkerResult.style.borderRadius = "var(--radius-md)";   /* ваби-саби геометрия: почти прямые углы */
        checkerResult.style.marginTop = "16px";
        checkerResult.style.border = `1px solid ${borderColor}`;
        checkerResult.style.borderLeftWidth = "3px";             /* «корешок» как в книгах вадзёку */
        checkerResult.style.background = "var(--bg-elevated)";
        checkerResult.style.boxShadow = "var(--shadow-sm)";

        checkerResult.innerHTML = `
            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-wrap: wrap;">
                <div style="width: 48px; height: 48px; border-radius: var(--radius-sm); background: ${bgColor}; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: ${textColor}; flex-shrink: 0;">
                    <i class="fas ${icon}"></i>
                </div>
                <div style="flex: 1; min-width: 200px;">
                    <div style="font-weight: 700; font-size: 1.1rem; color: var(--text-primary);">${title}</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--text-muted); word-break: break-all; margin-top: 4px;">${url}</div>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 500; color: ${textColor};">${Math.round(data.risk_score * 100)}%</div>
            </div>
            ${detailsHtml}
            <div class="result-title" hidden>${title}</div>
        `;

        // Счётчик лимита — мягкий триггер к апгрейду, пока человек «в потоке»
        if (typeof data.checks_remaining === "number") {
            const remaining = data.checks_remaining;
            const limitNote = document.createElement("p");
            limitNote.style.cssText = "margin-top:14px; font-size:0.85rem; color:var(--text-muted);";
            if (remaining > 2) {
                limitNote.textContent = `Осталось ${remaining} бесплатных проверок в этом месяце.`;
            } else {
                limitNote.innerHTML =
                    `Осталось ${remaining} бесплатных проверок. ` +
                    `<a href="checkout.html?plan=pro&trial=1" style="color:var(--accent-primary); font-weight:600;">Про без ограничений — 7 дней бесплатно →</a>`;
            }
            checkerResult.appendChild(limitNote);
        }
    }
});
// ===================================
// ПЛАВНЫЙ ПЕРЕХОД К СЕКЦИИ ПРИ КЛИКЕ ПО ЯКОРЮ (межстраничный)
// Если ссылка ведёт на другую страницу с #якорем — после загрузки
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
    } catch (e) { /* невалидный селектор — игнорируем */ }
})();

// ===================================
// ЭФФЕКТ «СЦЕНЫ» В СЕТКЕ ТАРИФОВ
// Когда мышь входит в сетку — карточки под ней «загораются»,
// остальные приглушаются (CSS-правило .pricing-grid.has-hover)
// ===================================
(function pricingGridScene() {
    const grid = document.getElementById('pricingGrid');
    if (!grid || !window.matchMedia('(pointer: fine)').matches) return;
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
// БЕСКОНЕЧНАЯ ЛЕНТА ОТЗЫВОВ (marquee)
// Дублируем набор карточек, чтобы цикл был непрерывным
// ===================================
(function testimonialMarquee() {
    const track = document.getElementById('testimonialsTrack');
    if (!track) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    track.setAttribute('aria-roledescription', 'carousel');
    track.insertAdjacentHTML('beforeend', track.innerHTML);
    track.querySelectorAll('.testimonial-card').forEach((c, i) => {
        if (i >= 4) c.setAttribute('aria-hidden', 'true');
    });
})();
