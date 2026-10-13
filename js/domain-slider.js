// ===================================
// DOMAIN SLIDER — движущаяся лента доменов
// -----------------------------------
// Верхняя дорожка — безопасные домены, нижняя — фишинговые.
// Для бесшовного CSS-цикла дорожка рендерится двумя одинаковыми
// половинами (каждая — набор, повторённый N раз), затем сдвигается
// на -50%. Клик по плашке подставляет домен в поле проверки.
//
// Обработчик клика навешивается один раз на дорожку (делегирование),
// поэтому клоны для второй половины остаются «живыми» без повторного
// навешивания слушателей.
// ===================================
(function domainSlider() {
    const root = document.querySelector('[data-domain-slider]');
    if (!root) return;
    // дорожки лежат внутри root, а <template>-шаблоны — в самой секции,
    // поэтому их ищем в общем контейнере
    const scope = root.closest('.domain-slider-section') || root;

    // Примеры для демонстрации — реальные домены сервисов,
    // фишинговые написаны по типичным приёмам подмены.
    const SAFE_DOMAINS = [
        'sberbank.ru',
        'gosuslugi.ru',
        'ozon.ru',
        'avito.ru',
        'yandex.ru',
        'vk.com',
        'wildberries.ru',
        'nalog.gov.ru',
        'tinkoff.ru',
        'market.yandex.ru'
    ];

    const THREAT_DOMAINS = [
        'sberbank-ru.com',
        'gos-uslugi.ru',
        'ozon-sale.ru',
        'avito-bonus.com',
        'ya-discount.ru',
        'vk-com.ru',
        'wlidberries.ru',
        'sber-online-bank.ru',
        'tinkoff-bonus.ru',
        'gosuslugi-vyplaty.ru'
    ];

    const safeTrack = root.querySelector('[data-track="safe"]');
    const threatTrack = root.querySelector('[data-track="threat"]');
    const safeTemplate = scope.querySelector('[data-template="safe"]');
    const threatTemplate = scope.querySelector('[data-template="threat"]');

    // Сколько раз повторить набор в одной половине — чтобы перекрыть
    // ширину экрана при любой вёрстке.
    const REPEATS = 3;

    function fullUrl(domain) {
        const slash = domain.indexOf('/');
        return slash === -1 ? `https://${domain}/` : `https://${domain}`;
    }

    function createChip(domain, kind, template) {
        const chip = template.content.firstElementChild.cloneNode(true);
        chip.classList.add(`domain-chip--${kind}`);

        // хост показываем основным цветом, хвост (путь) — приглушённо
        const slash = domain.indexOf('/');
        const host = slash === -1 ? domain : domain.slice(0, slash);
        const path = slash === -1 ? '' : domain.slice(slash);

        chip.querySelector('.domain-chip-host').textContent = host;
        const pathEl = chip.querySelector('.domain-chip-path');
        if (pathEl) pathEl.textContent = path;

        chip.dataset.url = fullUrl(domain);
        chip.setAttribute('title', `${host} — подставить в поле проверки`);
        chip.setAttribute('aria-label', kind === 'safe'
            ? `Безопасный домен ${host}`
            : `Подозрительный домен ${host}`);

        return chip;
    }

    function buildHalf(domains, kind, template) {
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < REPEATS; i++) {
            domains.forEach(domain => fragment.appendChild(createChip(domain, kind, template)));
        }
        return fragment;
    }

    function mountTrack(trackEl, domains, kind, template) {
        if (!trackEl || !template) return;

        // первая половина
        trackEl.appendChild(buildHalf(domains, kind, template));

        // вторая половина — точная копия первой (для сдвига на -50%)
        const clone = document.createDocumentFragment();
        Array.from(trackEl.children).forEach(node => clone.appendChild(node.cloneNode(true)));
        trackEl.appendChild(clone);
    }

    // Делегирование: один слушатель на дорожку, работает и для клонов
    function handleChipClick(event) {
        const chip = event.target.closest('.domain-chip');
        if (!chip) return;

        const url = chip.dataset.url;
        if (!url) return;

        const input = document.getElementById('urlInput');
        const checker = document.getElementById('checker');

        if (input) {
            input.value = url;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (checker) {
            checker.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (input) {
            // фокус — после прокрутки, чтобы не «дёргался» скролл
            setTimeout(() => input.focus({ preventScroll: true }), 450);
        }
    }

    mountTrack(safeTrack, SAFE_DOMAINS, 'safe', safeTemplate);
    mountTrack(threatTrack, THREAT_DOMAINS, 'threat', threatTemplate);

    [safeTrack, threatTrack].forEach(track => {
        if (track) track.addEventListener('click', handleChipClick);
    });
})();
