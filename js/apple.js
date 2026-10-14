// Scroll reveal
  const reveals = document.querySelectorAll('.reveal, .scale-reveal');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -80px 0px' });
  reveals.forEach(el => observer.observe(el));

  // Sticky CTA
  (function() {
    const sticky = document.getElementById('stickyCta');
    let shown = false;
    window.addEventListener('scroll', () => {
      if (!shown && window.scrollY > 600) {
        sticky.classList.add('visible');
        shown = true;
      }
    });
  })();
