// ===================================
// Правовые документы: «Политика конфиденциальности» и «Условия использования»
// Открываются модальным окном по клику на ссылку с data-legal="privacy|terms"
// ===================================
(function legalModal() {
    const modal = document.getElementById('legalModal');
    const titleEl = document.getElementById('legalModalTitle');
    const bodyEl = document.getElementById('legalModalBody');
    if (!modal || !titleEl || !bodyEl) return;

    function fillFrom(id) {
        const tpl = document.getElementById('legal-' + id);
        if (!tpl) return false;
        titleEl.textContent = id === 'privacy'
            ? 'Политика конфиденциальности'
            : 'Условия использования';
        bodyEl.innerHTML = '';
        bodyEl.appendChild(tpl.content.cloneNode(true));
        return true;
    }

    function open(id) {
        if (!fillFrom(id)) return;
        modal.hidden = false;
        document.body.classList.add('modal-open');
        const closeBtn = modal.querySelector('.legal-modal-close');
        if (closeBtn) closeBtn.focus();
    }

    function close() {
        if (modal.hidden) return;
        modal.hidden = true;
        document.body.classList.remove('modal-open');
    }

    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('[data-legal]');
        if (trigger) {
            e.preventDefault();
            open(trigger.getAttribute('data-legal'));
            return;
        }
        if (e.target.closest('[data-legal-close]')) {
            close();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') close();
    });
})();