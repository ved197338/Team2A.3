/**
 * INNOV8 // OPTINET - MONOCHROME PARTICLE & WAVE HARMONICS CANVAS
 * Strict Black & White / Grayscale aesthetic with smooth flowing physics.
 * Simulates high-dimensional transformer tokens as reactive fluid particles
 * that gracefully oscillate and deflect based on cursor interaction.
 */

(function () {
  'use strict';

  const canvas = document.getElementById('hero-ambient-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width, height, dpr;
  let mouse = { x: -1000, y: -1000, targetX: -1000, targetY: -1000, active: false };
  let animationFrameId;

  const PARTICLE_COUNT = 90;
  let particles = [];

  class Particle {
    constructor(x, y) {
      this.baseX = x;
      this.baseY = y;
      this.x = x;
      this.y = y;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.radius = 1.5 + Math.random() * 2.5;
      this.baseAlpha = 0.12 + Math.random() * 0.22;
      this.alpha = this.baseAlpha;
      this.phase = Math.random() * Math.PI * 2;
      this.speed = 0.008 + Math.random() * 0.012;
    }

    update(time) {
      // Harmonic wave flow
      const floatX = Math.sin(time * this.speed + this.phase) * 14;
      const floatY = Math.cos(time * (this.speed * 1.2) + this.phase) * 10;

      const targetX = this.baseX + floatX;
      const targetY = this.baseY + floatY;

      // Mouse magnetic reaction
      if (mouse.active) {
        const dx = this.x - mouse.x;
        const dy = this.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const maxDist = 220;

        if (dist < maxDist && dist > 0) {
          const force = (1 - dist / maxDist) * 35;
          this.x += (targetX + (dx / dist) * force - this.x) * 0.08;
          this.y += (targetY + (dy / dist) * force - this.y) * 0.08;
          this.alpha = Math.min(0.65, this.baseAlpha + (1 - dist / maxDist) * 0.4);
          return;
        }
      }

      this.x += (targetX - this.x) * 0.05;
      this.y += (targetY - this.y) * 0.05;
      this.alpha += (this.baseAlpha - this.alpha) * 0.05;
    }

    draw(ctx) {
      // Particle dot
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0, 0, 0, ${this.alpha})`;
      ctx.fill();

      // Delicate concentric ring
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius + 3, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0, 0, 0, ${this.alpha * 0.35})`;
      ctx.lineWidth = 0.6;
      ctx.stroke();
    }
  }

  function initParticles() {
    particles = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const x = Math.random() * width;
      const y = Math.random() * height;
      particles.push(new Particle(x, y));
    }
  }

  function resize() {
    dpr = window.devicePixelRatio || 1;
    width = canvas.parentElement.clientWidth;
    height = canvas.parentElement.clientHeight;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';

    ctx.scale(dpr, dpr);
    initParticles();
  }

  // Draw subtle nodal connection mesh in pure grayscale
  function drawMesh() {
    for (let i = 0; i < particles.length; i++) {
      const p1 = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const p2 = particles[j];
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 120) {
          const alpha = (1 - dist / 120) * 0.09;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(0, 0, 0, ${alpha})`;
          ctx.lineWidth = 0.6;
          ctx.stroke();
        }
      }
    }
  }

  let startTime = performance.now();

  function animate(now) {
    const time = (now - startTime) * 0.001;

    // Smooth cursor interpolation
    mouse.x += (mouse.targetX - mouse.x) * 0.1;
    mouse.y += (mouse.targetY - mouse.y) * 0.1;

    ctx.clearRect(0, 0, width, height);

    // Draw monochromatic mesh
    drawMesh();

    // Update and draw particles
    for (let i = 0; i < particles.length; i++) {
      particles[i].update(time);
      particles[i].draw(ctx);
    }

    animationFrameId = requestAnimationFrame(animate);
  }

  window.addEventListener('resize', resize);

  window.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    if (
      e.clientX >= rect.left &&
      e.clientX <= rect.right &&
      e.clientY >= rect.top &&
      e.clientY <= rect.bottom
    ) {
      mouse.targetX = e.clientX - rect.left;
      mouse.targetY = e.clientY - rect.top;
      mouse.active = true;
    } else {
      mouse.active = false;
    }
  });

  window.addEventListener('mouseleave', () => {
    mouse.active = false;
  });

  resize();
  animationFrameId = requestAnimationFrame(animate);
})();
