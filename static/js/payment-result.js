// Возврат с оплаты ЮKassa: payment-result.html?order=...
// Статус спрашиваем у нашего сервера, а он - у ЮKassa.
(function () {
    const { errorText } = window.PhishDetForms;
    const params = new URLSearchParams(window.location.search);
    const orderId = params.get('order');

    const title = document.getElementById('payTitle');
    const text = document.getElementById('payText');
    const details = document.getElementById('payDetails');
    const actions = document.getElementById('payActions');

    const POLL_INTERVAL_MS = 3000;
    const POLL_ATTEMPTS = 20; // около минуты

    const token = localStorage.getItem('access_token');
    if (!token) {
        const back = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.replace(`auth.html?mode=login&redirect=${back}`);
        return;
    }

    function show(heading, message, links, extra) {
        title.textContent = heading;
        text.textContent = message;
        details.hidden = !extra;
        details.textContent = extra || '';
        actions.innerHTML = links
            .map(([href, label, cls]) => `<a href="${href}" class="btn ${cls}">${label}</a>`)
            .join('');
        actions.hidden = links.length === 0;
    }

    function formatDate(iso) {
        if (!iso) return null;
        // Сервер отдаёт время в UTC без зоны - добавляем её явно
        const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z');
        return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    if (!orderId) {
        show('Платёж не найден', 'В адресе нет номера заказа. Статус подписки виден в личном кабинете.',
            [['dashboard.html', 'В личный кабинет', 'btn-verm']]);
        return;
    }

    let attempts = 0;

    async function poll() {
        attempts += 1;
        try {
            const response = await fetch(`/api/payment/status/${encodeURIComponent(orderId)}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.status === 401) {
                localStorage.removeItem('access_token');
                const back = encodeURIComponent(window.location.pathname + window.location.search);
                window.location.replace(`auth.html?mode=login&expired=1&redirect=${back}`);
                return;
            }

            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(errorText(data, 'Не удалось узнать статус платежа'));

            if (data.state === 'paid') {
                const until = formatDate(data.subscription_expires_at);
                show('Оплата прошла',
                    `Подписка «${data.plan_title}» активна${until ? ` до ${until}` : ''}.`,
                    [['index.html#checker', 'Проверить ссылку', 'btn-verm'], ['dashboard.html', 'В личный кабинет', 'btn-ink']]);
                return;
            }

            if (data.state === 'failed') {
                show('Оплата не прошла',
                    'Деньги не списаны. Можно попробовать ещё раз - например, другой картой.',
                    [[`checkout.html?plan=${encodeURIComponent(data.plan)}`, 'Попробовать снова', 'btn-verm'], ['pricing.html', 'К тарифам', 'btn-ink']]);
                return;
            }

            if (attempts >= POLL_ATTEMPTS) {
                show('Ждём подтверждение от банка',
                    'Банк ещё не прислал подтверждение. Если деньги списались, подписка включится автоматически в течение нескольких минут - статус виден в личном кабинете.',
                    [['dashboard.html', 'В личный кабинет', 'btn-verm']],
                    `Номер заказа: ${data.order_id}`);
                return;
            }

            setTimeout(poll, POLL_INTERVAL_MS);
        } catch (error) {
            show('Не удалось узнать статус', error.message,
                [['dashboard.html', 'В личный кабинет', 'btn-verm']]);
        }
    }

    poll();
})();
