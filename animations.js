/* INITIUM 3D Animation System — Auto-detecting, conflict-aware */
(function() {
  'use strict';

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) return;
  if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;
  gsap.registerPlugin(ScrollTrigger);

  function hasGSAP(el) {
    return gsap.getTweensOf(el).length > 0;
  }
  function hasScrollTrigger(el) {
    return ScrollTrigger.getAll().some(st => st.vars.trigger === el);
  }
  function isAnimated(el) {
    return hasGSAP(el) || hasScrollTrigger(el) || el.dataset.animLocked;
  }

  /* ── 1. Auto Hero Gradient Backgrounds ── */
  function initHeroGradients() {
    document.querySelectorAll('.hero, .page-hero, [class*="hero"]').forEach(h => {
      if (h.classList.contains('anim-gradient-bg') || h.classList.contains('anim-gradient-bg-dark')) return;
      h.classList.add('anim-gradient-bg');
    });
  }

  /* ── 2. Hero Title Character 3D Reveal (only if no existing GSAP) ── */
  function initHeroReveals() {
    document.querySelectorAll('.hero-title, .page-hero-title').forEach(title => {
      if (title.dataset.charRevealed || isAnimated(title)) return;
      title.dataset.charRevealed = '1';
      const text = title.textContent;
      title.innerHTML = '';
      const wrap = document.createElement('span');
      wrap.style.display = 'inline-block';
      wrap.style.whiteSpace = 'nowrap';
      text.split('').forEach(ch => {
        const span = document.createElement('span');
        span.textContent = ch === ' ' ? '\u00A0' : ch;
        span.style.display = 'inline-block';
        span.style.transformOrigin = '50% 100%';
        span.style.willChange = 'transform, opacity';
        wrap.appendChild(span);
      });
      title.appendChild(wrap);
      gsap.from(wrap.children, {
        scrollTrigger: { trigger: title, start: 'top 90%', toggleActions: 'play none none none' },
        rotateX: -85, y: 50, opacity: 0, duration: 0.9, stagger: 0.025, ease: 'power3.out',
      });
    });
  }

  /* ── 3. Section Title 3D Reveals (skip if already has GSAP) ── */
  function initSectionReveals() {
    const selectors = '.section-title, .page-section-title, .cta-title, .about-title, .service-content h3, .story-content h2, .apply-title, .vt-hero-title, .article-title';
    document.querySelectorAll(selectors).forEach((el, i) => {
      if (el.dataset.revealed || isAnimated(el)) return;
      el.dataset.revealed = '1';
      gsap.from(el, {
        scrollTrigger: { trigger: el, start: 'top 88%', toggleActions: 'play none none none' },
        y: 50, rotateX: 10, opacity: 0, duration: 1, delay: (i % 3) * 0.1, ease: 'power3.out',
      });
    });
  }

  /* ── 4. Generic Content Block 3D Reveals ── */
  function initContentReveals() {
    const blocks = document.querySelectorAll('.section-text, .about-text p, .service-desc, .testimonial-quote, .story-content p, .apply-desc, .vt-hero-desc');
    blocks.forEach((el, i) => {
      if (el.dataset.revealed || isAnimated(el)) return;
      el.dataset.revealed = '1';
      gsap.from(el, {
        scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none none' },
        y: 40, rotateX: 8, opacity: 0, duration: 0.9, delay: (i % 4) * 0.08, ease: 'power3.out',
      });
    });
  }

  /* ── 5. Counter Roll Animation (skip if already targeted) ── */
  function initCounters() {
    document.querySelectorAll('.stat-number[data-target], [data-count]').forEach(el => {
      const target = parseInt(el.dataset.target || el.dataset.count, 10);
      const suffix = el.dataset.suffix || '';
      if (!target || el.dataset.counterInit || isAnimated(el)) return;
      el.dataset.counterInit = '1';
      const obj = { val: 0 };
      ScrollTrigger.create({
        trigger: el, start: 'top 85%', once: true,
        onEnter: () => {
          gsap.to(obj, {
            val: target, duration: 2.2, ease: 'power2.out',
            onUpdate: () => { el.textContent = Math.round(obj.val) + suffix; }
          });
        }
      });
    });
  }

  /* ── 6. 3D Hover Tilt on Cards ── */
  function initTilt3D() {
    const cardSelectors = '.property-card, .service-card, .testimonial-card, .agent-card, .product-card, .stat-card, .value-card, .process-step, .launch-card, .blog-card, .news-card, .team-card';
    document.querySelectorAll(cardSelectors).forEach(card => {
      if (card.dataset.tiltInit) return;
      card.dataset.tiltInit = '1';
      card.classList.add('tilt-3d');
      const inner = card.querySelector('.tilt-3d-inner') || card;
      card.addEventListener('mousemove', e => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left, y = e.clientY - rect.top;
        const cx = rect.width / 2, cy = rect.height / 2;
        const rx = ((y - cy) / cy) * -7;
        const ry = ((x - cx) / cx) * 7;
        inner.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) scale3d(1.02,1.02,1.02)`;
      });
      card.addEventListener('mouseleave', () => {
        inner.style.transform = 'perspective(900px) rotateX(0) rotateY(0) scale3d(1,1,1)';
      });
    });
  }

  /* ── 7. Image Reveal Masks ── */
  function initImageReveals() {
    document.querySelectorAll('.about-img, .team-img, .story-img, .agent-photo, .blog-img, .news-img, .launch-img').forEach(img => {
      if (img.dataset.imgRevealed || isAnimated(img)) return;
      img.dataset.imgRevealed = '1';
      img.classList.add('img-reveal-3d');
      ScrollTrigger.create({ trigger: img, start: 'top 85%', once: true, onEnter: () => img.classList.add('revealed') });
    });
  }

  /* ── 8. Parallax (skip elements already parallaxed) ── */
  function initParallax() {
    document.querySelectorAll('.about-img, .hero-icon, .service-icon').forEach((el, i) => {
      if (isAnimated(el)) return;
      const speed = i % 2 === 0 ? -40 : 30;
      gsap.to(el, {
        scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: 1.5 },
        y: speed, ease: 'none',
      });
    });
  }

  /* ── 9. Magnetic Buttons ── */
  function initMagnetic() {
    document.querySelectorAll('.hero-cta, .cta-btn, .checkout-btn, .apply-btn, .contact-btn').forEach(btn => {
      if (btn.dataset.magneticInit) return;
      btn.dataset.magneticInit = '1';
      btn.classList.add('magnetic-btn');
      btn.addEventListener('mousemove', e => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        btn.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
      });
      btn.addEventListener('mouseleave', () => { btn.style.transform = 'translate(0,0)'; });
    });
  }

  /* ── 10. Divider scale reveal ── */
  function initDividers() {
    document.querySelectorAll('hr, .section-divider').forEach(div => {
      if (div.dataset.dividerInit) return;
      div.dataset.dividerInit = '1';
      div.classList.add('divider-3d');
      ScrollTrigger.create({ trigger: div, start: 'top 95%', once: true, onEnter: () => div.classList.add('revealed') });
    });
  }

  /* ── 11. Staggered grid reveals (only where disabled/no GSAP) ── */
  function initGridReveals() {
    const grids = ['.service-grid', '.property-grid', '.testimonial-grid', '.agent-grid', '.value-grid', '.process-grid', '.launch-grid', '.blog-grid', '.news-grid'];
    grids.forEach(selector => {
      document.querySelectorAll(selector).forEach(grid => {
        if (isAnimated(grid) || grid.dataset.gridRevealed) return;
        grid.dataset.gridRevealed = '1';
        const items = grid.children;
        gsap.from(items, {
          scrollTrigger: { trigger: grid, start: 'top 85%' },
          y: 60, rotateX: 12, opacity: 0, duration: 0.9, stagger: 0.1, ease: 'power3.out',
        });
      });
    });
  }

  /* ── 12. Floating ambient on icons (skip if already animated) ── */
  function initFloating() {
    document.querySelectorAll('.hero-icon, .service-icon').forEach((el, i) => {
      if (isAnimated(el)) return;
      gsap.to(el, {
        y: '+=10', rotateX: 3, duration: 4 + i,
        repeat: -1, yoyo: true, ease: 'sine.inOut',
      });
    });
  }

  /* ── 13. 3D entrance for CTA sections (if not already animated) ── */
  function initCTA3D() {
    document.querySelectorAll('.cta-section').forEach(cta => {
      if (isAnimated(cta)) return;
      const children = cta.querySelectorAll('.section-title, .section-text, .cta-btn');
      gsap.from(children, {
        scrollTrigger: { trigger: cta, start: 'top 80%' },
        y: 50, rotateX: 15, opacity: 0, duration: 1, stagger: 0.15, ease: 'power3.out',
      });
    });
  }

  /* ── 14. Dynamic content observer (for shop grids etc) ── */
  function initDynamicObserver() {
    const observer = new MutationObserver(() => {
      initTilt3D();
      initGridReveals();
      initMagnetic();
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  /* ── Init all ── */
  function initAll() {
    initHeroGradients();
    initHeroReveals();
    initSectionReveals();
    initContentReveals();
    initCounters();
    initTilt3D();
    initImageReveals();
    initParallax();
    initMagnetic();
    initDividers();
    initGridReveals();
    initFloating();
    initCTA3D();
    initDynamicObserver();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
