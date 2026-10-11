/**
 * INNOV8 // OPTINET - GSAP & INTERACTIVE ANIMATIONS
 * Implements smooth flowing scroll triggers, micro-animations,
 * accordion mechanics, and tab controllers matching Isomorphic Labs.
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. Accordion Controller (Exact Isomorphic Labs Accordion Behavior)
  // =========================================================================
  function initAccordions() {
    const accordions = document.querySelectorAll('.accordion-item');

    accordions.forEach((item) => {
      const trigger = item.querySelector('.accordion-trigger');
      const content = item.querySelector('.accordion-content');
      if (!trigger || !content) return;

      trigger.addEventListener('click', () => {
        const isOpen = item.classList.contains('is-open');

        // Close other accordions in the same list if desired
        const parentList = item.closest('.accordion-list');
        if (parentList) {
          parentList.querySelectorAll('.accordion-item').forEach((sibling) => {
            if (sibling !== item && sibling.classList.contains('is-open')) {
              sibling.classList.remove('is-open');
              const siblingContent = sibling.querySelector('.accordion-content');
              if (siblingContent) siblingContent.style.maxHeight = '0px';
            }
          });
        }

        if (isOpen) {
          item.classList.remove('is-open');
          content.style.maxHeight = '0px';
        } else {
          item.classList.add('is-open');
          content.style.maxHeight = content.scrollHeight + 40 + 'px';
        }
      });
    });
  }

  // =========================================================================
  // 2. Studio Tabs Controller (Studio Navigation)
  // =========================================================================
  function initStudioTabs() {
    const tabButtons = document.querySelectorAll('.studio-tab-btn');
    const tabPanels = document.querySelectorAll('.studio-content-panel');

    tabButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-tab');
        if (!targetId) return;

        tabButtons.forEach((b) => b.classList.remove('active'));
        tabPanels.forEach((p) => p.classList.remove('active'));

        btn.classList.add('active');
        const activePanel = document.getElementById(targetId);
        if (activePanel) {
          activePanel.classList.add('active');

          // Trigger resize for any child sliders or canvases
          window.dispatchEvent(new Event('resize'));
        }
      });
    });
  }

  // =========================================================================
  // 3. Smooth Anchor Scrolling & Active Link Highlighting
  // =========================================================================
  function initNavScroll() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach((link) => {
      link.addEventListener('click', (e) => {
        const targetId = link.getAttribute('href');
        if (!targetId || targetId === '#') return;

        const targetEl = document.querySelector(targetId);
        if (targetEl) {
          e.preventDefault();
          const navOffset = 80;
          const targetPosition = targetEl.getBoundingClientRect().top + window.pageYOffset - navOffset;

          window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
          });
        }
      });
    });

    // Update active nav link on scroll
    const sections = document.querySelectorAll('section[id]');
    window.addEventListener('scroll', () => {
      const scrollY = window.pageYOffset;

      sections.forEach((sec) => {
        const sectionTop = sec.offsetTop - 120;
        const sectionHeight = sec.offsetHeight;
        const sectionId = sec.getAttribute('id');

        if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
          document.querySelectorAll('.nav-link').forEach((l) => {
            l.classList.remove('active');
            if (l.getAttribute('href') === `#${sectionId}`) {
              l.classList.add('active');
            }
          });
        }
      });
    }, { passive: true });
  }

  // =========================================================================
  // 4. Copy-to-Clipboard Utility
  // =========================================================================
  function initCopyButtons() {
    const copyBtns = document.querySelectorAll('[data-copy-target]');

    copyBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-copy-target');
        const targetEl = document.getElementById(targetId);
        if (!targetEl) return;

        const text = targetEl.textContent || targetEl.innerText;
        navigator.clipboard.writeText(text).then(() => {
          const originalText = btn.textContent;
          btn.textContent = 'COPIED!';
          btn.style.color = '#16a34a';

          setTimeout(() => {
            btn.textContent = originalText;
            btn.style.color = '';
          }, 2000);
        });
      });
    });
  }

  // =========================================================================
  // 5. GSAP Scroll Animations & Reveals
  // =========================================================================
  function initGsapAnimations() {
    // Check if GSAP is available
    if (typeof gsap === 'undefined') {
      // Fallback CSS-based reveal if GSAP CDN is blocked
      document.querySelectorAll('.reveal-up').forEach((el) => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      });
      return;
    }

    // Register ScrollTrigger if available
    if (typeof ScrollTrigger !== 'undefined') {
      gsap.registerPlugin(ScrollTrigger);
    }

    // Hero Stagger Animation (Exact Isomorphic Timing)
    const heroBox1 = document.querySelector('[data-gsap="hero-box-1"]');
    const heroBox2 = document.querySelector('[data-gsap="hero-box-2"]');
    const heroBox3 = document.querySelector('[data-gsap="hero-box-3"]');

    if (heroBox1) {
      gsap.from(heroBox1, {
        opacity: 0,
        y: 40,
        duration: 0.8,
        ease: 'power2.out'
      });
    }

    if (heroBox2) {
      gsap.from(heroBox2, {
        opacity: 0,
        y: 40,
        duration: 0.8,
        delay: 0.15,
        ease: 'power2.out'
      });
    }

    if (heroBox3) {
      gsap.from(heroBox3, {
        opacity: 0,
        y: 40,
        duration: 0.8,
        delay: 0.3,
        ease: 'power2.out'
      });
    }

    // Staggered Cards Reveal on Scroll
    const cardGrids = document.querySelectorAll('.u-3cols, .u-4cols, .u-2cols');
    cardGrids.forEach((grid) => {
      const cards = grid.querySelectorAll('.card-cell');
      if (cards.length > 0 && typeof ScrollTrigger !== 'undefined') {
        gsap.from(cards, {
          opacity: 0,
          y: 35,
          duration: 0.7,
          stagger: 0.1,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: grid,
            start: 'top 85%',
            toggleActions: 'play none none none'
          }
        });
      }
    });

    // Animate KPI Numbers Counter
    const kpiElements = document.querySelectorAll('[data-counter-target]');
    kpiElements.forEach((el) => {
      const targetVal = parseFloat(el.getAttribute('data-counter-target'));
      const decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
      const prefix = el.getAttribute('data-prefix') || '';
      const suffix = el.getAttribute('data-suffix') || '';

      if (typeof ScrollTrigger !== 'undefined') {
        ScrollTrigger.create({
          trigger: el,
          start: 'top 90%',
          once: true,
          onEnter: () => {
            gsap.to({ val: 0 }, {
              val: targetVal,
              duration: 1.5,
              ease: 'power1.out',
              onUpdate: function () {
                el.textContent = prefix + this.targets()[0].val.toFixed(decimals) + suffix;
              }
            });
          }
        });
      }
    });
  }

  // =========================================================================
  // BOOTSTRAP
  // =========================================================================
  window.addEventListener('DOMContentLoaded', () => {
    initAccordions();
    initStudioTabs();
    initNavScroll();
    initCopyButtons();
    initGsapAnimations();
  });

})();
