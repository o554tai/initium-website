document.addEventListener('DOMContentLoaded', () => {
    // ===== PAGE LOADER =====
    const loader = document.querySelector('.page-loader');
    const loaderLetters = document.querySelectorAll('.loader-letter');
    const loaderProgress = document.querySelector('.loader-progress');

    const loaderTl = gsap.timeline();
    
    loaderTl
        .to(loaderLetters, {
            y: 0,
            opacity: 1,
            duration: 0.6,
            stagger: 0.08,
            ease: 'power3.out'
        })
        .to(loaderProgress, {
            width: '100%',
            duration: 1.2,
            ease: 'power2.inOut'
        }, '-=0.3')
        .to(loaderLetters, {
            y: -30,
            opacity: 0,
            duration: 0.4,
            stagger: 0.05,
            ease: 'power3.in'
        }, '+=0.2')
        .to(loaderProgress, {
            opacity: 0,
            duration: 0.3
        }, '<')
        .to(loader, {
            clipPath: 'inset(0 0 100% 0)',
            duration: 0.8,
            ease: 'power3.inOut',
            onComplete: () => {
                loader.style.display = 'none';
                initAnimations();
            }
        });

    function initAnimations() {
        // ===== LENIS SMOOTH SCROLL =====
        const lenis = new Lenis({
            duration: 1.2,
            easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            orientation: 'vertical',
            gestureOrientation: 'vertical',
            smoothWheel: true,
            wheelMultiplier: 1,
            touchMultiplier: 2,
        });

        function raf(time) {
            lenis.raf(time);
            requestAnimationFrame(raf);
        }
        requestAnimationFrame(raf);

        // Sync Lenis with GSAP ScrollTrigger
        lenis.on('scroll', ScrollTrigger.update);
        gsap.ticker.add((time) => {
            lenis.raf(time * 1000);
        });
        gsap.ticker.lagSmoothing(0);

        // Smooth scroll for nav links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    lenis.scrollTo(target, { offset: -80 });
                }
            });
        });

        // ===== SCROLL PROGRESS BAR =====
        const progressBar = document.querySelector('.scroll-progress-bar');
        gsap.to(progressBar, {
            width: '100%',
            ease: 'none',
            scrollTrigger: {
                trigger: document.body,
                start: 'top top',
                end: 'bottom bottom',
                scrub: 0.3
            }
        });

        // ===== NAVBAR SCROLL BEHAVIOR =====
        const navbar = document.querySelector('.navbar');
        let lastScroll = 0;

        ScrollTrigger.create({
            start: 'top -100',
            onUpdate: (self) => {
                if (self.scroll() > 100) {
                    navbar.classList.add('scrolled');
                } else {
                    navbar.classList.remove('scrolled');
                }
            }
        });

        // ===== CUSTOM CURSOR =====
        const cursor = document.querySelector('.cursor');
        const cursorDot = document.querySelector('.cursor-dot');
        const cursorOutline = document.querySelector('.cursor-outline');

        if (window.matchMedia('(pointer: fine)').matches) {
            let mouseX = 0, mouseY = 0;
            let dotX = 0, dotY = 0;
            let outlineX = 0, outlineY = 0;

            document.addEventListener('mousemove', (e) => {
                mouseX = e.clientX;
                mouseY = e.clientY;
            });

            function animateCursor() {
                dotX += (mouseX - dotX) * 0.2;
                dotY += (mouseY - dotY) * 0.2;
                outlineX += (mouseX - outlineX) * 0.1;
                outlineY += (mouseY - outlineY) * 0.1;

                cursorDot.style.left = dotX + 'px';
                cursorDot.style.top = dotY + 'px';
                cursorOutline.style.left = outlineX + 'px';
                cursorOutline.style.top = outlineY + 'px';

                requestAnimationFrame(animateCursor);
            }
            animateCursor();

            // Cursor hover states
            const hoverElements = document.querySelectorAll('a, button, [data-magnetic]');
            hoverElements.forEach(el => {
                el.addEventListener('mouseenter', () => cursor.classList.add('hover'));
                el.addEventListener('mouseleave', () => cursor.classList.remove('hover'));
            });
        }

        // ===== MAGNETIC BUTTONS =====
        const magneticElements = document.querySelectorAll('[data-magnetic]');
        magneticElements.forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                el.style.transform = `translate(${x * 0.3}px, ${y * 0.3}px)`;
            });
            el.addEventListener('mouseleave', () => {
                el.style.transform = 'translate(0, 0)';
            });
        });

        // ===== TEXT REVEAL ANIMATIONS =====
        // Hero title
        gsap.from('.hero-title .reveal-text', {
            y: 120,
            opacity: 0,
            duration: 1.2,
            stagger: 0.15,
            ease: 'power3.out',
            delay: 0.3
        });

        gsap.from('.hero-tag-wrapper', {
            y: 30,
            opacity: 0,
            duration: 0.8,
            ease: 'power3.out',
            delay: 0.1
        });

        gsap.from('.hero-subtitle', {
            y: 40,
            opacity: 0,
            duration: 1,
            ease: 'power3.out',
            delay: 0.6
        });

        gsap.from('.hero-buttons', {
            y: 40,
            opacity: 0,
            duration: 1,
            ease: 'power3.out',
            delay: 0.8
        });

        gsap.from('.hero-visual', {
            scale: 0.8,
            opacity: 0,
            duration: 1.5,
            ease: 'power3.out',
            delay: 0.4
        });

        // Section titles - scroll triggered
        document.querySelectorAll('.section-title .reveal-text').forEach(text => {
            gsap.from(text, {
                y: 80,
                opacity: 0,
                duration: 1,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: text,
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                }
            });
        });

        // Section tags
        document.querySelectorAll('.section-tag').forEach(tag => {
            gsap.from(tag, {
                y: 30,
                opacity: 0,
                duration: 0.8,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: tag,
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                }
            });
        });

        // Reveal fade elements
        document.querySelectorAll('.reveal-fade').forEach(el => {
            gsap.to(el, {
                y: 0,
                opacity: 1,
                duration: 1,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: el,
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                }
            });
        });

        // ===== FEATURE CARDS STAGGER =====
        gsap.from('.feature-card', {
            y: 60,
            opacity: 0,
            duration: 0.8,
            stagger: 0.15,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.features-grid',
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });

        // Feature icons animate in
        gsap.from('.feature-icon-wrapper', {
            scale: 0,
            opacity: 0,
            duration: 0.6,
            stagger: 0.1,
            ease: 'back.out(1.7)',
            scrollTrigger: {
                trigger: '.features-grid',
                start: 'top 75%',
                toggleActions: 'play none none none'
            }
        });

        // ===== PROJECT CARDS STAGGER =====
        gsap.from('.project-card', {
            y: 80,
            opacity: 0,
            duration: 1,
            stagger: 0.2,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.projects-grid',
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });

        // Project images parallax
        document.querySelectorAll('.project-image-inner').forEach(img => {
            gsap.to(img, {
                yPercent: -10,
                ease: 'none',
                scrollTrigger: {
                    trigger: img.closest('.project-card'),
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: 1
                }
            });
        });

        // ===== CTA SECTION =====
        gsap.from('.cta-title .reveal-text', {
            y: 80,
            opacity: 0,
            duration: 1,
            stagger: 0.15,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.cta-title',
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });

        // ===== PARALLAX ORBS =====
        gsap.to('.orb-1', {
            yPercent: -30,
            ease: 'none',
            scrollTrigger: {
                trigger: '.hero',
                start: 'top top',
                end: 'bottom top',
                scrub: 1
            }
        });

        gsap.to('.orb-2', {
            yPercent: 20,
            ease: 'none',
            scrollTrigger: {
                trigger: '.hero',
                start: 'top top',
                end: 'bottom top',
                scrub: 1
            }
        });

        // Section orbs parallax
        document.querySelectorAll('.section-bg .gradient-orb').forEach(orb => {
            gsap.to(orb, {
                yPercent: -40,
                ease: 'none',
                scrollTrigger: {
                    trigger: orb.closest('.section'),
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: 1
                }
            });
        });

        // ===== 3D TILT EFFECT =====
        const tiltCards = document.querySelectorAll('[data-tilt]');
        
        tiltCards.forEach(card => {
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                
                const rotateX = ((y - centerY) / centerY) * -8;
                const rotateY = ((x - centerX) / centerX) * 8;
                
                card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
                
                // Move glow with mouse
                const glow = card.querySelector('.card-glow');
                if (glow) {
                    glow.style.background = `radial-gradient(circle at ${x}px ${y}px, rgba(99,102,241,0.15), transparent 60%)`;
                }
            });
            
            card.addEventListener('mouseleave', () => {
                card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)';
            });
        });

        // ===== HERO ORBIT PARALLAX ON MOUSE MOVE =====
        const orbitSystem = document.querySelector('.orbit-system');
        if (orbitSystem && window.matchMedia('(pointer: fine)').matches) {
            document.querySelector('.hero').addEventListener('mousemove', (e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const x = (e.clientX - rect.left) / rect.width - 0.5;
                const y = (e.clientY - rect.top) / rect.height - 0.5;
                
                orbitSystem.style.transform = `translate(${x * 20}px, ${y * 20}px)`;
            });
        }

        // ===== MARQUEE SPEED ON SCROLL =====
        const marqueeTrack = document.querySelector('.marquee-track');
        if (marqueeTrack) {
            let currentSpeed = 30;
            ScrollTrigger.create({
                onUpdate: (self) => {
                    const velocity = Math.abs(self.getVelocity());
                    const newDuration = Math.max(10, 30 - velocity / 200);
                    if (Math.abs(newDuration - currentSpeed) > 2) {
                        currentSpeed = newDuration;
                        marqueeTrack.style.animationDuration = currentSpeed + 's';
                    }
                }
            });
        }

        // ===== FOOTER ENTRANCE =====
        gsap.from('.footer-brand', {
            y: 30,
            opacity: 0,
            duration: 0.8,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.footer',
                start: 'top 90%',
                toggleActions: 'play none none none'
            }
        });

        gsap.from('.footer-link', {
            y: 20,
            opacity: 0,
            duration: 0.6,
            stagger: 0.08,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.footer-links',
                start: 'top 90%',
                toggleActions: 'play none none none'
            }
        });

        // ===== SMOOTH SCROLL HINT =====
        gsap.from('.scroll-hint', {
            opacity: 0,
            y: 20,
            duration: 1,
            ease: 'power3.out',
            delay: 2
        });
    }
});
