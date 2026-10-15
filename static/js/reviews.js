// ===================================
// Отзывы в журнале
// -----------------------------------
// 1) Загружает опубликованные отзывы с /api/reviews и добавляет их к
//    свёрстанным примерам.
// 2) Показывает не больше трёх отзывов за раз. Кнопка «далее» справа
//    листает остальные - они заменяют то, что видно сейчас.
// 3) «Оставить отзыв» открывает модальное окно, форма шлёт POST
//    /api/reviews. Отзыв уходит на проверку администратору и попадает
//    в журнал только после одобрения.
// ===================================
(function reviews() {
    const notes = document.getElementById('notes');
    const modal = document.getElementById('reviewModal');
    if (!notes || !modal) return;

    const list = document.getElementById('notesList') || notes;
    const pager = document.getElementById('notesPager');
    const pagerCount = document.getElementById('notesPagerCount');
    const prevBtn = document.getElementById('notesPrev');
    const nextBtn = document.getElementById('notesNext');

    const form = document.getElementById('reviewForm');
    const statusEl = document.getElementById('reviewStatus');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    const API = 'api/reviews';
    const PAGE_SIZE = 3;

    // Свёрстанные примеры - они есть даже без бэкенда
    let allNotes = Array.from(list.querySelectorAll('.note'));
    let page = 0;

    function makeNote(item) {
        const note = document.createElement('div');
        note.className = 'note reveal active';

        const text = document.createElement('p');
        text.className = 'note-text';
        text.textContent = '«' + item.text + '»';
        note.appendChild(text);

        const name = (item.name || '').trim();
        const role = (item.role || '').trim();
        const meta = [name || 'гость', role].filter(Boolean).join(' · ');

        const metaEl = document.createElement('p');
        metaEl.className = 'note-meta';
        metaEl.textContent = meta;
        note.appendChild(metaEl);

        return note;
    }

    function pad(n) { return (n < 10 ? '0' : '') + n; }

    function totalPages() {
        return Math.max(1, Math.ceil(allNotes.length / PAGE_SIZE));
    }

    function render() {
        if (!allNotes.length) return;

        const pages = totalPages();
        if (page >= pages) page = 0;
        if (page < 0) page = pages - 1;

        const start = page * PAGE_SIZE;
        const slice = allNotes.slice(start, start + PAGE_SIZE);

        list.innerHTML = '';
        slice.forEach(function (note) {
            note.classList.add('active');
            list.appendChild(note);
        });

        if (pager) {
            pager.hidden = allNotes.length <= PAGE_SIZE;
            if (pagerCount) pagerCount.textContent = pad(page + 1) + ' / ' + pad(pages);
        }
    }

    function step(delta) { page += delta; render(); }

    if (prevBtn) prevBtn.addEventListener('click', function () { step(-1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { step(1); });

    // Первый показ - показываем то, что уже свёрстано
    render();

    // --- Загрузка опубликованных отзывов ---------------------------
    fetch(API, { headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (items) {
            if (!Array.isArray(items) || !items.length) return;
            const fresh = items.map(makeNote); // последние сверху
            allNotes = fresh.concat(allNotes);
            page = 0;
            render();
        })
        .catch(function () { /* нет бэкенда - не страшно */ });

    // --- Открытие/закрытие модального окна -------------------------
    function open() {
        modal.hidden = false;
        document.body.classList.add('modal-open');
        if (statusEl) { statusEl.textContent = ''; statusEl.className = 'review-status'; }
        const first = form ? form.querySelector('input,textarea') : null;
        if (first) first.focus();
    }

    function close() {
        if (modal.hidden) return;
        modal.hidden = true;
        document.body.classList.remove('modal-open');
    }

    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-review-open]')) { open(); return; }
        if (e.target.closest('[data-review-close]')) { close(); }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') close();
    });

    if (!form) return;

    // --- Отправка нового отзыва на проверку ------------------------
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const data = new FormData(form);
        const text = (data.get('text') || '').trim();

        if (text.length < 5) {
            if (statusEl) { statusEl.textContent = 'Напишите хотя бы пару слов.'; statusEl.className = 'review-status is-error'; }
            return;
        }

        if (submitBtn) { submitBtn.disabled = true; }
        if (statusEl) { statusEl.textContent = 'Отправляем…'; statusEl.className = 'review-status'; }

        fetch(API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({
                name: (data.get('name') || '').trim() || null,
                role: (data.get('role') || '').trim() || null,
                text: text
            })
        })
            .then(function (r) {
                if (!r.ok) throw new Error('request failed');
                return r.json();
            })
            .then(function () {
                form.reset();
                if (statusEl) { statusEl.textContent = 'Отзыв отправлен на проверку. Он появится в журнале после одобрения.'; statusEl.className = 'review-status is-ok'; }
                window.setTimeout(close, 2600);
            })
            .catch(function () {
                if (statusEl) { statusEl.textContent = 'Не получилось отправить. Попробуйте позже.'; statusEl.className = 'review-status is-error'; }
            })
            .then(function () {
                if (submitBtn) { submitBtn.disabled = false; }
            });
    });
})();
