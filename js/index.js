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
                showStatus("🔒 Для проверки ссылок необходимо войти в аккаунт. Перенаправляем...", "warning");
                sessionStorage.setItem("pending_url", url); // Сохраняем ссылку

                setTimeout(() => {
                    window.location.href = "auth.html";
                }, 1500);
                return;
            }

            // ЕСЛИ АВТОРИЗОВАН - ПРОВЕРЯЕМ
            showStatus("⏳ Анализируем ссылку с помощью ИИ...", "loading");
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
                    throw new Error(`⚠️ Лимит исчерпан (${data.detail.checks_used}/${data.detail.checks_limit}). <a href="pricing.html" style="color: var(--accent-primary); text-decoration: underline;">Купить тариф</a>`);
                }

                if (!response.ok) {
                    throw new Error("Ошибка при проверке URL");
                }

                const data = await response.json();
                displayResult(data, url);
                showStatus(`✅ Проверка завершена! Осталось попыток: ${data.checks_remaining === 9999 ? '∞' : data.checks_remaining}`, "success");

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
            checkStatus.style.background = "rgba(99, 102, 241, 0.1)";
            checkStatus.style.border = "1px solid rgba(99, 102, 241, 0.3)";
            checkStatus.style.color = "var(--accent-primary, #6366f1)";
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
        checkerResult.style.borderRadius = "16px";
        checkerResult.style.marginTop = "16px";
        checkerResult.style.border = `1px solid ${borderColor}`;
        checkerResult.style.background = "var(--bg-card)";

        checkerResult.innerHTML = `
            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-wrap: wrap;">
                <div style="width: 48px; height: 48px; border-radius: 50%; background: ${bgColor}; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: ${textColor}; flex-shrink: 0;">
                    <i class="fas ${icon}"></i>
                </div>
                <div style="flex: 1; min-width: 200px;">
                    <div style="font-weight: 700; font-size: 1.1rem; color: var(--text-primary);">${title}</div>
                    <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--text-muted); word-break: break-all; margin-top: 4px;">${url}</div>
                </div>
                <div style="font-size: 1.5rem; font-weight: 800; color: ${textColor};">${Math.round(data.risk_score * 100)}%</div>
            </div>
            ${detailsHtml}
        `;
    }
});