// ===================================
// PRICING: подсветка карточки под курсором + переход к плану из URL
// ===================================
(function () {
    const cards = document.querySelectorAll('.plan-card');
    const finePointer = window.matchMedia('(pointer: fine)').matches;

    if (finePointer) {
        cards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                card.style.setProperty('--card-mouse-x', (e.clientX - rect.left) + 'px');
                card.style.setProperty('--card-mouse-y', (e.clientY - rect.top) + 'px');
            });
            card.addEventListener('mouseenter', () => {
                cards.forEach(c => c.classList.remove('is-lit'));
                card.classList.add('is-lit');
            });
            card.addEventListener('mouseleave', () => card.classList.remove('is-lit'));
        });
    }

    // Плавный переход и подсветка плана, указанного в URL (?plan=pro)
    const selectedPlan = new URLSearchParams(window.location.search).get('plan');
    if (!selectedPlan) return;

    const planElement = document.getElementById(selectedPlan);
    if (!planElement) return;

    setTimeout(() => {
        planElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        planElement.classList.add('is-lit');
        setTimeout(() => planElement.classList.remove('is-lit'), 2500);
    }, 300);
})();

// Межстраничные якоря (#basic/#pro/#corporate) - плавный довод после загрузки
(function smoothHashScroll() {
    const hash = window.location.hash;
    if (!hash || hash.length < 2) return;
    try {
        const el = document.querySelector(hash);
        if (el) requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    } catch (e) {}
})();
