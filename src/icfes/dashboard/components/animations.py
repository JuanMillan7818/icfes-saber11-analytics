import streamlit.components.v1 as components

_JS = """
<script>
(function() {
    'use strict';

    const pwin = window.parent;
    const pdoc = pwin.document;

    // Guard: run only once per full page load
    if (pwin.__icfes_anim_init) return;
    pwin.__icfes_anim_init = true;

    // ── Load anime.js into parent frame ───────────────────────────────
    function loadAnime(cb) {
        if (typeof pwin.anime !== 'undefined') { cb(); return; }
        const s = pdoc.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.2/anime.min.js';
        s.onload = cb;
        pdoc.head.appendChild(s);
    }

    // ── Particle canvas ───────────────────────────────────────────────
    function initCanvas() {
        if (pdoc.getElementById('particle-canvas')) return;
        const canvas = pdoc.createElement('canvas');
        canvas.id = 'particle-canvas';
        canvas.style.cssText = [
            'position:fixed', 'top:0', 'left:0',
            'width:100%', 'height:100%',
            'pointer-events:none', 'z-index:0', 'opacity:0.3',
        ].join(';');
        pdoc.body.appendChild(canvas);

        const ctx = canvas.getContext('2d');
        let W, H;
        const particles = [];

        function resize() {
            W = canvas.width  = pwin.innerWidth;
            H = canvas.height = pwin.innerHeight;
        }
        resize();
        pwin.addEventListener('resize', resize);

        for (let i = 0; i < 50; i++) {
            particles.push({
                x: Math.random() * W,
                y: Math.random() * H,
                r: Math.random() * 1.3 + 0.3,
                dx: (Math.random() - 0.5) * 0.22,
                dy: (Math.random() - 0.5) * 0.22,
                a:  Math.random() * 0.45 + 0.08,
            });
        }

        (function draw() {
            ctx.clearRect(0, 0, W, H);
            particles.forEach(p => {
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(56,189,248,${p.a})`;
                ctx.fill();
                p.x += p.dx; p.y += p.dy;
                if (p.x < 0 || p.x > W) p.dx *= -1;
                if (p.y < 0 || p.y > H) p.dy *= -1;
            });
            pwin.requestAnimationFrame(draw);
        })();
    }

    // ── Section card stagger entrance ─────────────────────────────────
    const _cardsAnimated = new pwin.WeakSet();
    function animateCards() {
        const anime = pwin.anime;
        if (!anime) return;
        const cards = [...pdoc.querySelectorAll('.section-card')]
            .filter(c => !_cardsAnimated.has(c));
        if (!cards.length) return;
        cards.forEach(c => _cardsAnimated.add(c));
        anime({
            targets: cards,
            opacity: [0, 1],
            translateY: [20, 0],
            delay: anime.stagger(70, { start: 150 }),
            duration: 550,
            easing: 'cubicBezier(0.22, 1, 0.36, 1)',
        });
    }

    // ── Tab glow pulse on active ───────────────────────────────────────
    let _tabAnim = null;
    function pulseActiveTab() {
        const anime = pwin.anime;
        if (!anime) return;
        const activeTab = pdoc.querySelector('[aria-selected="true"][data-baseweb="tab"]');
        if (!activeTab) return;
        if (_tabAnim) { try { _tabAnim.pause(); } catch(e) {} }
        _tabAnim = anime({
            targets: activeTab,
            boxShadow: [
                '0 0 18px rgba(56,189,248,0.15)',
                '0 0 34px rgba(56,189,248,0.32)',
                '0 0 18px rgba(56,189,248,0.15)',
            ],
            duration: 2200,
            easing: 'easeInOutSine',
            loop: true,
        });
    }

    // ── Bootstrap ─────────────────────────────────────────────────────
    function boot() {
        initCanvas();
        loadAnime(() => {
            setTimeout(animateCards,   700);
            setTimeout(pulseActiveTab, 900);

            // Re-animate on Streamlit rerenders with debounce
            let _debounce = null;
            const observer = new pwin.MutationObserver(() => {
                clearTimeout(_debounce);
                _debounce = setTimeout(() => {
                    animateCards();
                    pulseActiveTab();
                }, 300);
            });
            observer.observe(pdoc.body, { childList: true, subtree: false });
        });
    }

    if (pdoc.readyState === 'loading') {
        pdoc.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
</script>
"""


def render_animations():
    components.html(_JS, height=0)
