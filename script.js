document.addEventListener('DOMContentLoaded', () => {
    // ===== PAGE LOADER =====
    const loader = document.querySelector('.page-loader');
    const logoPaths = document.querySelectorAll('.logo-path');
    const loaderLetters = document.querySelectorAll('.loader-letter');
    const loaderProgress = document.querySelector('.loader-progress');

    const loaderTl = gsap.timeline();

    // Logo stroke draw-on animation
    loaderTl
        .to(logoPaths, {
            strokeDashoffset: 0,
            duration: 1.2,
            stagger: 0.15,
            ease: 'power2.inOut'
        })
        .to(loaderLetters, {
            y: 0,
            opacity: 1,
            duration: 0.6,
            stagger: 0.08,
            ease: 'power3.out'
        }, '-=0.6')
        .to(loaderProgress, {
            width: '100%',
            duration: 1.0,
            ease: 'power2.inOut'
        }, '-=0.5')
        .to(loaderLetters, {
            y: -30,
            opacity: 0,
            duration: 0.4,
            stagger: 0.05,
            ease: 'power3.in'
        }, '+=0.2')
        .to(logoPaths, {
            opacity: 0,
            duration: 0.3
        }, '<')
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

        // ===== CURSOR SPOTLIGHT =====
        const spotlight = document.querySelector('.cursor-spotlight');
        if (spotlight && window.matchMedia('(pointer: fine)').matches) {
            document.addEventListener('mousemove', (e) => {
                spotlight.style.setProperty('--spotlight-x', e.clientX + 'px');
                spotlight.style.setProperty('--spotlight-y', e.clientY + 'px');
            });
        }

        // ===== MAGNETIC BUTTONS (ENHANCED) =====
        const magneticElements = document.querySelectorAll('[data-magnetic]');
        magneticElements.forEach(el => {
            el.addEventListener('mousemove', (e) => {
                const rect = el.getBoundingClientRect();
                const x = e.clientX - rect.left - rect.width / 2;
                const y = e.clientY - rect.top - rect.height / 2;
                el.style.transform = `translate(${x * 0.35}px, ${y * 0.35}px)`;
            });
            el.addEventListener('mouseleave', () => {
                el.style.transform = 'translate(0, 0)';
                el.style.transition = 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
                setTimeout(() => { el.style.transition = ''; }, 500);
            });
        });

        // ===== PARTICLE CONSTELLATION =====
        const particleCanvas = document.getElementById('particle-canvas');
        if (particleCanvas) {
            const ctx = particleCanvas.getContext('2d');
            let particles = [];
            let animationId;
            const isTouchDevice = window.matchMedia('(pointer: coarse)').matches;

            function resizeCanvas() {
                const hero = document.querySelector('.hero');
                particleCanvas.width = hero.offsetWidth;
                particleCanvas.height = hero.offsetHeight;
            }
            resizeCanvas();
            window.addEventListener('resize', resizeCanvas);

            const particleCount = isTouchDevice ? 30 : 60;
            const connectionDistance = 120;
            const mouseRadius = 150;

            class Particle {
                constructor() {
                    this.x = Math.random() * particleCanvas.width;
                    this.y = Math.random() * particleCanvas.height;
                    this.vx = (Math.random() - 0.5) * 0.5;
                    this.vy = (Math.random() - 0.5) * 0.5;
                    this.radius = Math.random() * 2 + 1;
                }

                update(mouse) {
                    this.x += this.vx;
                    this.y += this.vy;

                    // Bounce off edges
                    if (this.x < 0 || this.x > particleCanvas.width) this.vx *= -1;
                    if (this.y < 0 || this.y > particleCanvas.height) this.vy *= -1;

                    // Mouse interaction
                    if (mouse.x !== null && mouse.y !== null) {
                        const dx = mouse.x - this.x;
                        const dy = mouse.y - this.y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < mouseRadius) {
                            const force = (mouseRadius - dist) / mouseRadius;
                            this.vx -= (dx / dist) * force * 0.5;
                            this.vy -= (dy / dist) * force * 0.5;
                        }
                    }

                    // Damping
                    this.vx *= 0.99;
                    this.vy *= 0.99;
                }

                draw() {
                    ctx.beginPath();
                    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                    ctx.fillStyle = 'rgba(129, 140, 248, 0.6)';
                    ctx.fill();
                }
            }

            const mouse = { x: null, y: null };

            particleCanvas.addEventListener('mousemove', (e) => {
                const rect = particleCanvas.getBoundingClientRect();
                mouse.x = e.clientX - rect.left;
                mouse.y = e.clientY - rect.top;
            });

            particleCanvas.addEventListener('mouseleave', () => {
                mouse.x = null;
                mouse.y = null;
            });

            for (let i = 0; i < particleCount; i++) {
                particles.push(new Particle());
            }

            function drawConnections() {
                for (let i = 0; i < particles.length; i++) {
                    for (let j = i + 1; j < particles.length; j++) {
                        const dx = particles[i].x - particles[j].x;
                        const dy = particles[i].y - particles[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);

                        if (dist < connectionDistance) {
                            const opacity = (1 - dist / connectionDistance) * 0.3;
                            const gradient = ctx.createLinearGradient(
                                particles[i].x, particles[i].y,
                                particles[j].x, particles[j].y
                            );
                            gradient.addColorStop(0, `rgba(99, 102, 241, ${opacity})`);
                            gradient.addColorStop(1, `rgba(192, 132, 252, ${opacity})`);

                            ctx.beginPath();
                            ctx.strokeStyle = gradient;
                            ctx.lineWidth = 1;
                            ctx.moveTo(particles[i].x, particles[i].y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.stroke();
                        }
                    }
                }
            }

            function animateParticles() {
                ctx.clearRect(0, 0, particleCanvas.width, particleCanvas.height);

                particles.forEach(p => {
                    p.update(mouse);
                    p.draw();
                });

                drawConnections();
                animationId = requestAnimationFrame(animateParticles);
            }
            animateParticles();

            // Pause when not visible
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        if (!animationId) animateParticles();
                    } else {
                        cancelAnimationFrame(animationId);
                        animationId = null;
                    }
                });
            });
            observer.observe(particleCanvas);
        }

        // ===== FILM GRAIN OVERLAY =====
        const grainCanvas = document.getElementById('grain-canvas');
        if (grainCanvas) {
            const grainCtx = grainCanvas.getContext('2d');
            let grainAnimationId;

            function resizeGrain() {
                grainCanvas.width = window.innerWidth;
                grainCanvas.height = window.innerHeight;
            }
            resizeGrain();
            window.addEventListener('resize', resizeGrain);

            function renderGrain() {
                const imageData = grainCtx.createImageData(grainCanvas.width, grainCanvas.height);
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    const value = Math.random() * 255;
                    data[i] = value;
                    data[i + 1] = value;
                    data[i + 2] = value;
                    data[i + 3] = 255;
                }
                grainCtx.putImageData(imageData, 0, 0);
                grainAnimationId = requestAnimationFrame(renderGrain);
            }
            renderGrain();
        }

        // ===== SCROLL-VELOCITY SKEW =====
        let currentSkew = 0;
        const skewElements = document.querySelectorAll('.feature-card, .project-card, .section-title');

        lenis.on('scroll', ({ velocity }) => {
            const targetSkew = Math.max(-3, Math.min(3, velocity * 0.02));
            currentSkew += (targetSkew - currentSkew) * 0.1;

            skewElements.forEach(el => {
                el.style.transform = `skewY(${currentSkew}deg)`;
            });
        });

        // ===== TEXT SCRAMBLE =====
        class TextScramble {
            constructor(el) {
                this.el = el;
                this.chars = '!<>-_\\/[]{}--=+*^?#________';
                this.originalText = el.dataset.text || el.innerText;
                this.update = this.update.bind(this);
            }

            scramble() {
                this.frame = 0;
                this.queue = [];
                const length = this.originalText.length;
                for (let i = 0; i < length; i++) {
                    this.queue.push({
                        from: this.chars[Math.floor(Math.random() * this.chars.length)],
                        to: this.originalText[i],
                        start: Math.floor(Math.random() * 20),
                        end: Math.floor(Math.random() * 20) + 20
                    });
                }
                cancelAnimationFrame(this.frameRequest);
                this.frameRequest = requestAnimationFrame(this.update);
            }

            update() {
                let output = '';
                let complete = 0;
                for (let i = 0; i < this.queue.length; i++) {
                    let { from, to, start, end } = this.queue[i];
                    let char = from;
                    if (this.frame >= end) {
                        complete++;
                        char = to;
                    } else if (this.frame >= start) {
                        if (Math.random() < 0.28) {
                            char = this.chars[Math.floor(Math.random() * this.chars.length)];
                        } else {
                            char = to;
                        }
                    }
                    output += char;
                }
                this.el.innerText = output;
                if (complete === this.queue.length) {
                    return;
                } else {
                    this.frame++;
                    this.frameRequest = requestAnimationFrame(this.update);
                }
            }
        }

        const scrambleTexts = document.querySelectorAll('.scramble-text');
        scrambleTexts.forEach(el => {
            const scrambler = new TextScramble(el);
            ScrollTrigger.create({
                trigger: el,
                start: 'top 85%',
                onEnter: () => scrambler.scramble(),
                once: true
            });
        });

        // ===== TEXT REVEAL ANIMATIONS =====
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

        // Section reveals
        gsap.utils.toArray('.reveal-text').forEach(text => {
            if (!text.closest('.hero-title')) {
                gsap.from(text, {
                    y: 100,
                    opacity: 0,
                    duration: 1.2,
                    ease: 'power3.out',
                    scrollTrigger: {
                        trigger: text,
                        start: 'top 85%',
                        toggleActions: 'play none none none'
                    }
                });
            }
        });

        gsap.utils.toArray('.reveal-fade').forEach(el => {
            gsap.from(el, {
                y: 40,
                opacity: 0,
                duration: 1,
                ease: 'power3.out',
                scrollTrigger: {
                    trigger: el,
                    start: 'top 85%',
                    toggleActions: 'play none none none'
                }
            });
        });

        // Feature cards stagger
        gsap.from('.feature-card', {
            y: 60,
            opacity: 0,
            duration: 1,
            stagger: 0.15,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.features-grid',
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });

        // Project cards stagger
        gsap.from('.project-card', {
            y: 80,
            opacity: 0,
            duration: 1.2,
            stagger: 0.2,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.projects-grid',
                start: 'top 80%',
                toggleActions: 'play none none none'
            }
        });

        // Parallax orbs
        gsap.utils.toArray('.gradient-orb').forEach(orb => {
            gsap.to(orb, {
                yPercent: -30,
                ease: 'none',
                scrollTrigger: {
                    trigger: orb.closest('section'),
                    start: 'top bottom',
                    end: 'bottom top',
                    scrub: 1
                }
            });
        });

        // ===== 3D CARD TILT + GLOW =====
        const tiltCards = document.querySelectorAll('[data-tilt]');
        tiltCards.forEach(card => {
            const glow = card.querySelector('.card-glow');

            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                const cx = rect.width / 2;
                const cy = rect.height / 2;
                const rx = ((y - cy) / cy) * -8;
                const ry = ((x - cx) / cx) * 8;

                card.style.transform = `perspective(1000px) rotateX(${rx}deg) rotateY(${ry}deg) scale3d(1.02, 1.02, 1.02)`;

                if (glow) {
                    glow.style.setProperty('--glow-x', x + 'px');
                    glow.style.setProperty('--glow-y', y + 'px');
                }
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)';
            });
        });

        // ===== BLOB PATH MORPHING =====
        const blobPaths = document.querySelectorAll('.blob-path, .blob-path-slow');
        blobPaths.forEach((path, index) => {
            const originalD = path.getAttribute('d');
            // Create a slightly varied path by shifting values
            const variations = [
                originalD,
                originalD.replace(/(\d+)/g, (match) => {
                    const num = parseInt(match);
                    const offset = (Math.random() - 0.5) * 40;
                    return Math.max(0, Math.round(num + offset)).toString();
                })
            ];

            gsap.to(path, {
                attr: { d: variations[1] },
                duration: 8 + index * 2,
                repeat: -1,
                yoyo: true,
                ease: 'sine.inOut'
            });
        });

        // ===== FOOTER ENTRANCE =====
        gsap.from('.footer-brand', {
            y: 30,
            opacity: 0,
            duration: 1,
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
            duration: 0.8,
            stagger: 0.1,
            ease: 'power3.out',
            scrollTrigger: {
                trigger: '.footer',
                start: 'top 90%',
                toggleActions: 'play none none none'
            }
        });

        // ===== NAV LOGO IDLE PULSE =====
        const navLogo = document.querySelector('.nav-logo-mark');
        if (navLogo) {
            gsap.to(navLogo, {
                scale: 1.05,
                duration: 2,
                repeat: -1,
                yoyo: true,
                ease: 'sine.inOut'
            });
        }
    }
});
