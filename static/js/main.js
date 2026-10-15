// ===================================
// HEADER SCROLL
// ===================================
const header = document.getElementById('header');

const progressBar = document.getElementById('scrollProgressBar');

window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }

    // тонкая линия прогресса чтения вверху страницы
    if (progressBar) {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        const p = max > 0 ? Math.min(window.scrollY / max, 1) : 0;
        progressBar.style.width = (p * 100).toFixed(2) + '%';
    }
}, { passive: true });

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

// лёгкий каскад: элементы внутри одной секции появляются лесенкой
document.querySelectorAll('section').forEach(section => {
    section.querySelectorAll('.reveal').forEach((el, i) => {
        el.style.transitionDelay = Math.min(i, 5) * 70 + 'ms';
    });
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
        const href = this.getAttribute('href');
        if (!href || href === '#' || href === '#!') return; // ссылки-заглушки - оставляем своему обработчику
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ===================================
// МАГНИТНЫЕ КНОПКИ - кнопка мягко «тянется» к курсору
// (приём с сайтов-референсов; на тач-устройствах отключён)
// ===================================
(function initMagnetic() {
    if (!window.matchMedia('(pointer: fine)').matches) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    document.querySelectorAll('.magnetic').forEach(btn => {
        let raf = null;
        btn.addEventListener('mousemove', (e) => {
            if (raf) return;
            raf = requestAnimationFrame(() => {
                raf = null;
                const r = btn.getBoundingClientRect();
                const x = (e.clientX - r.left - r.width / 2) * 0.25;
                const y = (e.clientY - r.top - r.height / 2) * 0.35;
                btn.style.transform = `translate(${x}px, ${y}px)`;
            });
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transition = 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
            btn.style.transform = '';
            setTimeout(() => { btn.style.transition = ''; }, 500);
        });
    });
})();

// ===================================
// SCRAMBLE-ДЕКОД - текст «раскодировывается» при появлении
// (фишка blackwood.dev: символы перебираются до финального слова)
// ===================================
(function initScramble() {
    const els = document.querySelectorAll('[data-scramble]');
    if (!els.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    // Шифр - только латиница/цифры/символы, без иероглифов (философия бренда)
    const cipherChars = Array.from('01!<>-_\\/[]{}=+*^?#ABCDEFXYZKMNPRST');

    function scrambleTo(el, finalText) {
        // поколение анимации - чтобы остановить старую цепочку при уходе из зоны видимости
        const seq = (parseInt(el.dataset.scrambleSeq, 10) || 0) + 1;
        el.dataset.scrambleSeq = String(seq);
        el.dataset.scrambling = '1';

        // Во время раскодировки случайные символы меняют ширину строки, и
        // заголовок «падает» на вторую строку - это выглядит как лаг.
        // Если финальный текст умещается в одну строку, на время анимации
        // запрещаем перенос и фиксируем высоту: блок остаётся на месте.
        el.textContent = finalText;
        const cs = getComputedStyle(el);
        let lineH = parseFloat(cs.lineHeight);
        if (!lineH) lineH = parseFloat(cs.fontSize) * 1.2;
        const rect = el.getBoundingClientRect();
        if (rect.height <= lineH * 1.6) el.style.whiteSpace = 'nowrap';
        el.style.minHeight = Math.round(rect.height) + 'px';

        const frame = [];
        const len = finalText.length;
        // Изначальная скорость: символы перебираются на каждом кадре экрана,
        // время раскодировки не зависит от длины текста
        for (let i = 0; i < len; i++) {
            const start = Math.floor(Math.random() * 16);
            const end = start + 8 + Math.floor(Math.random() * 16);
            frame.push({ from: null, to: finalText[i], start, end, char: null });
        }
        let tick = 0;
        const run = () => {
            if (!el.isConnected) return;
            // анимацию прервали (уехали из зоны видимости) - цепочку останавливаем
            if (parseInt(el.dataset.scrambleSeq, 10) !== seq) return;
            let out = '';
            let done = 0;
            for (const f of frame) {
                if (tick >= f.end) { out += f.to; done++; }
                else if (tick >= f.start) {
                    if (!f.char || Math.random() < 0.28) {
                        f.char = f.to === ' ' ? ' ' : cipherChars[Math.floor(Math.random() * cipherChars.length)];
                    }
                    out += `<span style="opacity:.45">${f.char}</span>`;
                } else { out += '&nbsp;'; }
            }
            el.innerHTML = out;
            if (done === len) {
                el.dataset.scrambling = '';
                el.style.whiteSpace = '';
                el.style.minHeight = '';
                return;
            }
            tick++;
            requestAnimationFrame(run);
        };
        run();
    }

    const obs = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const el = entry.target;
            if (entry.isIntersecting) {
                // уже раскодируется - не запускаем второй раз
                if (el.dataset.scrambling === '1') return;
                scrambleTo(el, el.dataset.scramble);
            } else {
                // секция ушла из зоны видимости: останавливаем анимацию и
                // возвращаем финальный текст, чтобы при обратном скролле
                // эффект раскодировки сработал снова
                el.dataset.scrambleSeq = String((parseInt(el.dataset.scrambleSeq, 10) || 0) + 1);
                el.dataset.scrambling = '';
                el.style.whiteSpace = '';
                el.style.minHeight = '';
                el.innerHTML = el.dataset.scramble;
            }
        });
    }, { threshold: 0.4 });

    els.forEach(el => obs.observe(el));
})();
