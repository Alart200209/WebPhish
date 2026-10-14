// ===================================
// Модерация отзывов
// -----------------------------------
// Доступна только администратору. Показывает отзывы, ждущие решения, и
// уже опубликованные. Админ может одобрить отзыв, снять его с публикации
// или удалить совсем. Пока отзыв не одобрен, он не виден на лендинге.
// ===================================
(function adminModeration() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'auth.html';
        return;
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
            localStorage.removeItem('access_token');
            window.location.href = 'index.html';
        });
    }

    const pendingList = document.getElementById('pendingList');
    const publishedList = document.getElementById('publishedList');
    const flash = document.getElementById('modFlash');

    let pending = [];
    let published = [];

    function setFlash(text, kind) {
        if (!flash) return;
        flash.textContent = text || '';
        flash.className = 'mod-flash' + (kind ? ' is-' + kind : '');
    }

    function fmtDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d.getTime())) return '';
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
    }

    async function api(path, options) {
        options = options || {};
        const headers = Object.assign(
            { 'Authorization': 'Bearer ' + token, 'Accept': 'application/json' },
            options.headers || {}
        );
        const res = await fetch(path, Object.assign({}, options, { headers }));

        if (res.status === 401 || res.status === 403) {
            const err = new Error('unauthorized');
            err.auth = true;
            throw err;
        }
        if (!res.ok) throw new Error('request failed');
        return res.status === 204 ? null : res.json();
    }

    function makeButton(label, cls, onClick) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = cls;
        b.textContent = label;
        b.addEventListener('click', onClick);
        return b;
    }

    function emptyNode(text) {
        const p = document.createElement('p');
        p.className = 'mod-empty';
        p.textContent = text;
        return p;
    }

    function reviewNode(review, status) {
        const item = document.createElement('div');
        item.className = 'mod-review';

        const main = document.createElement('div');

        const text = document.createElement('p');
        text.className = 'mod-review-text';
        text.textContent = '«' + review.text + '»';
        main.appendChild(text);

        const meta = document.createElement('div');
        meta.className = 'mod-review-meta';

        const badge = document.createElement('span');
        badge.className = 'check-status ' + status;
        badge.textContent = status === 'pending' ? 'на проверке' : 'в журнале';
        meta.appendChild(badge);

        const who = document.createElement('span');
        const name = (review.name || '').trim() || 'гость';
        const role = (review.role || '').trim();
        who.textContent = role ? name + ' · ' + role : name;
        meta.appendChild(who);

        const when = fmtDate(review.created_at);
        if (when) {
            const dateEl = document.createElement('span');
            dateEl.textContent = when;
            meta.appendChild(dateEl);
        }
        main.appendChild(meta);
        item.appendChild(main);

        const actions = document.createElement('div');
        actions.className = 'mod-review-actions';

        if (status === 'pending') {
            actions.appendChild(makeButton('Одобрить', 'btn btn-verm btn-sm', function () { moderate(review.id, true); }));
            actions.appendChild(makeButton('Удалить', 'btn btn-ink btn-sm', function () { remove(review.id); }));
        } else {
            actions.appendChild(makeButton('Снять', 'btn btn-ink btn-sm', function () { moderate(review.id, false); }));
            actions.appendChild(makeButton('Удалить', 'btn btn-ink btn-sm', function () { remove(review.id); }));
        }
        item.appendChild(actions);

        return item;
    }

    function renderList(container, items, status, emptyText) {
        if (!container) return;
        container.innerHTML = '';
        if (!items.length) {
            container.appendChild(emptyNode(emptyText));
            return;
        }
        items.forEach(function (review) {
            container.appendChild(reviewNode(review, status));
        });
    }

    function render() {
        renderList(pendingList, pending, 'pending', 'Пока никто не ждёт решения.');
        renderList(publishedList, published, 'published', 'В журнале пока нет отзывов.');

        const p = document.getElementById('pendingCount');
        const pub = document.getElementById('publishedCount');
        const total = document.getElementById('totalCount');
        if (p) p.textContent = pending.length;
        if (pub) pub.textContent = published.length;
        if (total) total.textContent = pending.length + published.length;
    }

    async function load() {
        try {
            const result = await Promise.all([
                api('/api/admin/reviews?status_filter=pending'),
                api('/api/admin/reviews?status_filter=published')
            ]);
            pending = result[0] || [];
            published = result[1] || [];
            render();
        } catch (e) {
            if (e && e.auth) {
                window.location.href = 'auth.html';
                return;
            }
            setFlash('Не удалось загрузить отзывы.', 'error');
        }
    }

    async function moderate(id, isPublished) {
        setFlash('Сохраняем…', '');
        try {
            await api('/api/admin/reviews/' + id, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_published: isPublished })
            });
            setFlash(isPublished ? 'Отзыв опубликован.' : 'Отзыв снят с публикации.', 'ok');
            await load();
        } catch (e) {
            if (e && e.auth) { window.location.href = 'auth.html'; return; }
            setFlash('Не получилось сохранить.', 'error');
        }
    }

    async function remove(id) {
        setFlash('Удаляем…', '');
        try {
            await api('/api/admin/reviews/' + id, { method: 'DELETE' });
            setFlash('Отзыв удалён.', 'ok');
            await load();
        } catch (e) {
            if (e && e.auth) { window.location.href = 'auth.html'; return; }
            setFlash('Не получилось удалить.', 'error');
        }
    }

    function showDenied() {
        const dash = document.querySelector('.dash');
        if (!dash) return;
        dash.innerHTML =
            '<div class="mod-denied">' +
            '<p class="hand" style="font-size:1.6rem;color:var(--ink-3);">сюда вход только по пропуску</p>' +
            '<p>Модерация отзывов доступна администратору. Войдите под админской учётной записью.</p>' +
            '<a href="dashboard.html" class="btn btn-ink">В кабинет</a> ' +
            '<a href="auth.html" class="btn btn-verm">Сменить аккаунт</a>' +
            '</div>';
    }

    async function init() {
        try {
            const me = await api('/api/auth/me');
            if (!me || !me.is_admin) {
                showDenied();
                return;
            }
            const emailEl = document.getElementById('adminEmail');
            if (emailEl) emailEl.textContent = me.email;
            await load();
        } catch (e) {
            if (e && e.auth) { window.location.href = 'auth.html'; return; }
            showDenied();
        }
    }

    init();
})();
