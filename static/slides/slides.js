/**
 * INNOV8 // OPTINET — SLIDE PRESENTATION CONTROLLER
 * Pure content presentation with smooth slide transitions.
 * Keyboard controls, wheel debouncing, and lineless scenario switcher.
 */

(function () {
  'use strict';

  const viewport = document.getElementById('slides-viewport');
  const slides = document.querySelectorAll('.slide');
  const counterEl = document.getElementById('slide-counter');
  const btnPrev = document.getElementById('btn-prev-slide');
  const btnNext = document.getElementById('btn-next-slide');

  let currentSlide = 0;
  const totalSlides = slides.length;
  let isNavigating = false;

  const numBtns = document.querySelectorAll('.slide-num-btn');

  function updateActiveIndicators(index) {
    if (counterEl) {
      const curStr = String(index + 1).padStart(2, '0');
      const totStr = String(totalSlides).padStart(2, '0');
      counterEl.textContent = `${curStr} / ${totStr}`;
    }
    numBtns.forEach((btn, idx) => {
      btn.classList.toggle('active', idx === index);
    });
  }

  // =========================================================================
  // 1. Slide Navigation Mechanics
  // =========================================================================
  function goToSlide(index, instant = false) {
    if (index < 0 || index >= totalSlides) return;
    currentSlide = index;

    const targetSlide = slides[index];
    if (targetSlide) {
      if (instant) {
        viewport.scrollTop = targetSlide.offsetTop;
      } else {
        targetSlide.scrollIntoView({ behavior: 'smooth' });
      }
    }

    slides.forEach((s, idx) => {
      s.classList.toggle('is-active', idx === index);
    });

    updateActiveIndicators(index);

    isNavigating = true;
    setTimeout(() => {
      isNavigating = false;
    }, 600);
  }

  function nextSlide() {
    if (currentSlide < totalSlides - 1) {
      goToSlide(currentSlide + 1);
    }
  }

  function prevSlide() {
    if (currentSlide > 0) {
      goToSlide(currentSlide - 1);
    }
  }

  // =========================================================================
  // 2. Event Listeners & Input Controls
  // =========================================================================
  if (btnNext) btnNext.addEventListener('click', nextSlide);
  if (btnPrev) btnPrev.addEventListener('click', prevSlide);

  numBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetIndex = parseInt(btn.getAttribute('data-goto'), 10);
      if (!isNaN(targetIndex)) {
        goToSlide(targetIndex);
      }
    });
  });

  // Keyboard navigation (Arrow keys, Spacebar, Page Up/Down)
  window.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
      e.preventDefault();
      nextSlide();
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft' || e.key === 'PageUp') {
      e.preventDefault();
      prevSlide();
    }
  });

  // Track scroll position
  let scrollTimeout;
  viewport.addEventListener('scroll', () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      const scrollPos = viewport.scrollTop + viewport.clientHeight / 2;
      slides.forEach((s, idx) => {
        if (scrollPos >= s.offsetTop && scrollPos < s.offsetTop + s.clientHeight) {
          if (currentSlide !== idx) {
            currentSlide = idx;
            slides.forEach((sl, i) => sl.classList.toggle('is-active', i === idx));
            updateActiveIndicators(idx);
          }
        }
      });
    }, 50);
  }, { passive: true });

  // Wheel debouncing for silky-smooth slide flips
  let lastWheelTime = 0;
  window.addEventListener('wheel', (e) => {
    const now = Date.now();
    if (now - lastWheelTime < 650) return;

    if (Math.abs(e.deltaY) > 25) {
      lastWheelTime = now;
      if (e.deltaY > 0) {
        nextSlide();
      } else {
        prevSlide();
      }
    }
  }, { passive: true });

  // =========================================================================
  // 3. Workload Scenario Switcher (Slide 7)
  // =========================================================================
  const SCENARIOS = {
    checkpoint: {
      tier: "COLD_HDD",
      quant: "DYNAMIC_INT8_QUANT_DEDUP (0.25x)",
      delta: "-63.75 TB (75% smaller)",
      savings: "$10,608.00 / month (97.5% reduction)",
      rationale: "Model weights idle for 42 days. Converting to INT8 numbers cuts size by 75% and moves data to cheap Cold HDD, saving $10.6k/mo with zero math loss.",
      cmd: "python -m torch.quantization.quantize_dynamic --dtype qint8 --weights /mnt/storage/ai-checkpoint-01 && zfs set compression=zstd-19 pool/vol-ai-ckpt-01 && kubectl annotate pv pv-ai-ckpt-01 storage.k8s.io/tier=cold-hdd-compressed --overwrite"
    },
    oltp: {
      tier: "HOT_NVME",
      quant: "RAW_NO_COMPRESSION (1.0x)",
      delta: "0.0 TB (Keeps full speed)",
      savings: "$0.00 / month (Protects 0.8ms speed)",
      rationale: "Live high-traffic database. Needs maximum speed. Kept on fastest NVMe drive with real-time priority so users experience zero lag.",
      cmd: "blockdev --setra 8192 /dev/nvme0n1p2 && ionice -c 1 -n 0 -p 4912 && kubectl patch pv pv-oltp-db-prod --type=merge -p '{\"spec\":{\"storageClassName\":\"fast-nvme-sc\"}}'"
    },
    logs: {
      tier: "WARM_SSD",
      quant: "ZSTD_DICTIONARY_ARCHIVE (0.15x)",
      delta: "-38.25 TB (85% smaller)",
      savings: "$3,825.00 / month (85.0% reduction)",
      rationale: "Old server logs and debug text files. Compressing with Zstandard shrinks space by 85% while still opening fast when needed for audits.",
      cmd: "zstd -19 --rm /mnt/logs/production-*.log -o /mnt/logs/archive-2026.zst && fstrim -v /mnt/logs && aws s3 cp /mnt/logs/archive-2026.zst s3://innov8-warm-store/"
    },
    glacier: {
      tier: "ARCHIVE_GLACIER",
      quant: "GZIP_DEFLATE_STREAM (0.25x)",
      delta: "-465.00 TB (75% smaller)",
      savings: "$7,192.00 / month (95.0% reduction)",
      rationale: "Old compliance files untouched for >180 days. Encrypts with AES-256 for security and moves to Amazon Glacier Deep Archive at under $0.001 per GB.",
      cmd: "cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 /dev/mapper/vol-archive-99 && aws s3 cp /dev/mapper/vol-archive-99 s3://innov8-deep-archive/ --storage-class DEEP_ARCHIVE"
    },
    host: {
      tier: "LOCAL_HYBRID",
      quant: "MULTI_CATEGORY_COMPACTION",
      delta: "-821.7 MB (38.4% space reclaimed)",
      savings: "$133.60 / month ($1,603.20 / year)",
      rationale: "Scanned 1,616 files on your laptop across 5 categories: INT8 on AI models, zip on old logs and code repos, and cache cleanup. 100% loss-free.",
      cmd: "python -c \"import optinet_innov8; optinet_innov8.optimize_host_storage('/home/april')\" && df -h /dev/nvme0n1p2"
    }
  };

  const scenarioBtns = document.querySelectorAll('[data-scenario]');
  const scTier = document.getElementById('sc-tier');
  const scQuant = document.getElementById('sc-quant');
  const scDelta = document.getElementById('sc-delta');
  const scSavings = document.getElementById('sc-savings');
  const scRationale = document.getElementById('sc-rationale');
  const scCmd = document.getElementById('sc-cmd');

  scenarioBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-scenario');
      const data = SCENARIOS[key];
      if (!data) return;

      scenarioBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      if (scTier) scTier.textContent = data.tier;
      if (scQuant) scQuant.textContent = data.quant;
      if (scDelta) scDelta.textContent = data.delta;
      if (scSavings) scSavings.textContent = data.savings;
      if (scRationale) scRationale.textContent = data.rationale;
      if (scCmd) scCmd.textContent = data.cmd;
    });
  });

  goToSlide(0, true);

  // =========================================================================
  // 4. Live Simulated Training Progress Ticker (Active Epoch 06/08)
  // =========================================================================
  let progressPct = 78.4;
  let samplesDone = 39200;
  const progressBars = document.querySelectorAll('.progress-bar-fill');
  const heroProgressVal = document.getElementById('hero-progress-val');

  setInterval(() => {
    if (progressPct < 79.8) {
      progressPct += 0.1;
      samplesDone += 50;
      progressBars.forEach(bar => {
        bar.style.width = `${progressPct.toFixed(1)}%`;
      });
      if (heroProgressVal) {
        heroProgressVal.textContent = `${progressPct.toFixed(1)}% COMPLETED`;
      }
    }
  }, 4000);

})();
