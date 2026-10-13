// ===================================
// HEADER SCROLL
// ===================================
const header = document.getElementById('header');

window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }
});

// ===================================
// MOBILE MENU
// ===================================
const mobileToggle = document.getElementById('mobileToggle');
const nav = document.getElementById('nav');

if (mobileToggle && nav) {
    mobileToggle.addEventListener('click', () => {
        mobileToggle.classList.toggle('active');
        nav.classList.toggle('active');
    });

    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            mobileToggle.classList.remove('active');
            nav.classList.remove('active');
        });
    });
}

// ===================================
// SCROLL REVEAL
// ===================================
const revealElements = document.querySelectorAll('.reveal');

const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('active');
        }
    });
}, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
});

revealElements.forEach(el => revealObserver.observe(el));

// ===================================
// КУРСОР-ПРОЖЕКТОР
// Тёплый свет следует за мышью; карточки с классом
// .card-spotlight подсвечиваются изнутри в точке курсора
// ===================================
(function initSpotlight() {
    const finePointer = window.matchMedia('(pointer: fine)').matches;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!finePointer || reducedMotion) return;

    document.body.classList.add('has-spotlight');

    let rafId = null;
    let lastX = 0, lastY = 0;

    document.addEventListener('mousemove', (e) => {
        lastX = e.clientX;
        lastY = e.clientY;
        if (rafId) return;
        rafId = requestAnimationFrame(() => {
            rafId = null;
            document.documentElement.style.setProperty('--mouse-x', lastX + 'px');
            document.documentElement.style.setProperty('--mouse-y', lastY + 'px');

            const card = document.elementFromPoint(lastX, lastY)?.closest('.card-spotlight');
            if (card) {
                const rect = card.getBoundingClientRect();
                card.style.setProperty('--card-mouse-x', (lastX - rect.left) + 'px');
                card.style.setProperty('--card-mouse-y', (lastY - rect.top) + 'px');
            }
        });
    }, { passive: true });
})();

// ===================================
// SMOOTH SCROLL
// ===================================
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});