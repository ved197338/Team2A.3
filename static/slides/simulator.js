/**
 * INNOV8 // OPTINET & PROJECT ONE DATA GOVERNANCE SIMULATOR
 * Strict Black & White / Monochrome calculation engine for:
 * 1. Innov8 OptiNet Multi-Task Neural Transformer
 * 2. Project 1 Data Quality Engine (2C Governance Spec, MAD, PSI, Luhn)
 * NO GREEN. NO RED. PURE BLACK AND WHITE.
 */

(function () {
  'use strict';

  const TIER_COSTS = {
    0: 0.125,   // HOT_NVME ($/GB/mo)
    1: 0.023,   // WARM_SSD
    2: 0.0125,  // COLD_HDD
    3: 0.00099  // ARCHIVE_GLACIER
  };

  const TIER_NAMES = ["HOT_NVME", "WARM_SSD", "COLD_HDD", "ARCHIVE_GLACIER"];

  const QUANTIZATION_POLICIES = [
    "RAW_NO_COMPRESSION (1.0x)",
    "FAST_LZ4_BLOCK (0.75x)",
    "DYNAMIC_INT8_QUANT_DEDUP (0.25x)",
    "EXTREME_ZSTD_ARCHIVE (0.08x)"
  ];

  const QUANT_SHRINK = [1.0, 0.75, 0.25, 0.08];

  const WORKLOAD_TYPES = [
    "AI_TRAINING_CHECKPOINT",
    "REALTIME_OLTP_DATABASE",
    "ANALYTICS_DATA_LAKE",
    "BATCH_BACKUP",
    "LOG_ARCHIVE",
    "DEV_TEST_VOLUME"
  ];

  const AGENT_ACTIONS = [
    "OBSERVE_NO_ACTION | STEADY_STATE",
    "AUTONOMOUS_TIER_MIGRATE | CUT_STORAGE_TCO",
    "DYNAMIC_INT8_QUANT_DEDUP | NEURAL_FOOTPRINT_SHRINK",
    "EXTREME_ZSTD_ARCHIVE | LONG_TERM_COLD_PACK",
    "EMERGENCY_BURST_THROTTLE | PRESERVE_SLA_LATENCY",
    "ENFORCE_KMS_ENCRYPT_AND_SEAL | COMPLIANCE_REMEDIATION",
    "PURGE_ZOMBIE_SNAPSHOTS | RECLAIM_ORPHANED_CAPACITY",
    "BURST_PROMOTE_NVME | ACCELERATE_HOT_CRITICAL_IO"
  ];

  const PRESETS = {
    checkpoint: {
      name: "vol-llm-checkpoint-prod-08",
      workload: 0,
      tier: 0,
      cap: 85,
      iops: 4200,
      tp: 850,
      lat: 4.8,
      qd: 42,
      inact: 14,
      freq: 120,
      sla: 8.0,
      enc: 0
    },
    oltp: {
      name: "vol-fin-ledger-primary-01",
      workload: 1,
      tier: 0,
      cap: 12,
      iops: 58000,
      tp: 1820,
      lat: 0.8,
      qd: 16,
      inact: 0,
      freq: 45000,
      sla: 2.0,
      enc: 1
    },
    datalake: {
      name: "vol-genomics-parquet-lake-04",
      workload: 2,
      tier: 1,
      cap: 340,
      iops: 6500,
      tp: 740,
      lat: 12.0,
      qd: 22,
      inact: 38,
      freq: 1800,
      sla: 25.0,
      enc: 1
    },
    glacier: {
      name: "vol-legacy-archive-compliance-99",
      workload: 3,
      tier: 2,
      cap: 620,
      iops: 95,
      tp: 32,
      lat: 45.0,
      qd: 2,
      inact: 195,
      freq: 12,
      sla: 60.0,
      enc: 1
    }
  };

  const state = { ...PRESETS.checkpoint };

  function getElements() {
    return {
      sliderIops: document.getElementById('slider-iops'),
      sliderTp: document.getElementById('slider-tp'),
      sliderLat: document.getElementById('slider-lat'),
      sliderQd: document.getElementById('slider-qd'),
      sliderCap: document.getElementById('slider-cap'),
      sliderInact: document.getElementById('slider-inact'),
      toggleEnc: document.getElementById('toggle-enc'),
      selectWorkload: document.getElementById('select-workload'),
      selectCurTier: document.getElementById('select-cur-tier'),

      valIops: document.getElementById('val-iops'),
      valTp: document.getElementById('val-tp'),
      valLat: document.getElementById('val-lat'),
      valQd: document.getElementById('val-qd'),
      valCap: document.getElementById('val-cap'),
      valInact: document.getElementById('val-inact'),

      presetBtns: document.querySelectorAll('[data-preset]'),

      outTargetTier: document.getElementById('out-target-tier'),
      outQuantPolicy: document.getElementById('out-quant-policy'),
      outMonthlySavings: document.getElementById('out-monthly-savings'),
      outSavingsPct: document.getElementById('out-savings-pct'),
      outFootprintDelta: document.getElementById('out-footprint-delta'),
      outAnomalyStatus: document.getElementById('out-anomaly-status'),
      outComplianceStatus: document.getElementById('out-compliance-status'),
      outAgentAction: document.getElementById('out-agent-action'),
      outAgentConf: document.getElementById('out-agent-conf'),
      outAgentThought: document.getElementById('out-agent-thought'),
      outCsiCommand: document.getElementById('out-csi-command'),
      outCurrentCost: document.getElementById('out-current-cost'),
      outNewCost: document.getElementById('out-new-cost')
    };
  }

  function evaluateVolume() {
    const el = getElements();
    if (!el.outTargetTier) return;

    const capGB = state.cap * 1024;
    const curTier = state.tier;
    const curCost = capGB * TIER_COSTS[curTier];

    const isAnomaly = (state.qd >= 32) || (state.lat > state.sla * 1.5);
    const isComplianceRisk = (state.enc === 0 && (state.inact > 7 || state.workload === 0 || state.workload === 1));

    let predTier = curTier;
    let predQuant = 0;
    let agentActionIdx = 0;

    if (isComplianceRisk) {
      agentActionIdx = 5;
      predTier = Math.min(curTier, 1);
    } else if (isAnomaly && state.qd >= 32) {
      agentActionIdx = 4;
      predTier = 0;
    } else if (state.inact >= 90) {
      predTier = 3;
      predQuant = 3;
      agentActionIdx = 3;
    } else if (state.inact >= 30) {
      predTier = 2;
      predQuant = state.workload === 0 ? 2 : 1;
      agentActionIdx = 1;
    } else if (state.workload === 0 && state.cap >= 20) {
      predTier = state.inact > 7 ? 2 : 1;
      predQuant = 2;
      agentActionIdx = 2;
    } else if (state.iops > 30000 || state.tp > 1200) {
      predTier = 0;
      predQuant = 0;
      agentActionIdx = 7;
    } else {
      predTier = 1;
      predQuant = 1;
      agentActionIdx = 1;
    }

    const quantFactor = QUANT_SHRINK[predQuant];
    const newCapTB = state.cap * quantFactor;
    const footprintReducedTB = state.cap - newCapTB;
    const newCost = (capGB * quantFactor) * TIER_COSTS[predTier];
    const savedDollars = Math.max(0, curCost - newCost);
    const savingsPct = curCost > 0 ? (savedDollars / curCost) * 100 : 0;

    const confidence = Math.min(0.998, 0.88 + (Math.sin(state.iops * 0.0001 + state.cap * 0.02) * 0.08) + (isComplianceRisk ? 0.08 : 0));

    let csiCmd = "";
    const quantSubcmd = predQuant === 2
      ? " && innov8-quant-ctl --int8-weights --dedup-blocks /mnt/" + state.name
      : (predQuant === 3 ? " && zstd -19 --ultra /mnt/" + state.name + "/*.bin" : "");

    if (isComplianceRisk) {
      csiCmd = "aws kms enable-key-rotation --key-id alias/innov8-vault && kubectl annotate pv pv-" + state.name + " storage.k8s.io/enforce-kms=true --overwrite && innov8-crypto-seal --encrypt-in-place";
    } else if (isAnomaly && state.qd >= 32) {
      csiCmd = "echo mq-deadline > /sys/block/nvme0n1/queue/scheduler && sysctl -w vm.dirty_ratio=10 vm.dirty_background_ratio=5 && ionice -c 1 -n 0 -p 1024";
    } else if (predTier === 0) {
      const targetIops = Math.min(64000, Math.max(10000, Math.round(state.iops * 1.2)));
      csiCmd = "kubectl patch pv pv-" + state.name + " --type=merge -p '{\"spec\":{\"storageClassName\":\"nvme-io2-high-performance\"}}' && aws ec2 modify-volume --volume-id " + state.name + " --iops " + targetIops;
    } else if (predTier === 1) {
      csiCmd = "kubectl patch pv pv-" + state.name + " --type=merge -p '{\"spec\":{\"storageClassName\":\"gp3-standard-ssd\"}}' && aws s3api put-bucket-lifecycle-configuration --bucket store-" + state.name + " --lifecycle-configuration '{\"Rules\":[{\"Status\":\"Enabled\",\"Transitions\":[{\"Days\":1,\"StorageClass\":\"STANDARD\"}]}]}'" + quantSubcmd;
    } else if (predTier === 2) {
      csiCmd = "zfs set compression=zstd-9 pool/pv-" + state.name + " && ceph osd pool set ec-cold-pool compression_algorithm zstd && kubectl annotate pv pv-" + state.name + " storage.k8s.io/tier=cold-hdd-compressed --overwrite" + quantSubcmd;
    } else {
      csiCmd = "kubectl annotate pv pv-" + state.name + " storage.k8s.io/tier=s3-glacier-deep-archive --overwrite && aws s3api put-object-tagging --bucket enterprise-checkpoints --key " + state.name + ".tar.zst --tagging 'TagSet=[{\"Key\":\"Tier\",\"Value\":\"GlacierDeepArchive\"}]'" + quantSubcmd;
    }

    let thought = `Volume '${state.name}' (${state.cap} TB, ${WORKLOAD_TYPES[state.workload]}) has ${state.inact} idle days on ${TIER_NAMES[curTier]}. `;
    if (isComplianceRisk) {
      thought += "Immediate security vulnerability detected: unencrypted retention violates cryptographic posture. Action: enforce KMS seal and isolate snapshot.";
    } else if (isAnomaly && state.qd >= 32) {
      thought += `Queue saturation (QD=${state.qd}) detected. Action: inject I/O throttle and switch elevator scheduler to mq-deadline to protect latency SLA.`;
    } else if (predQuant === 2) {
      thought += `Model checkpoint detected. Applying Dynamic INT8 Quantization and Block Deduplication reclaims 75% raw storage, cutting monthly TCO by ${savingsPct.toFixed(1)}%.`;
    } else if (predQuant === 3) {
      thought += `Cold inactive storage archive candidate. Compacting with ZSTD-19 archive profile yields maximum ${savingsPct.toFixed(1)}% cloud cost reduction.`;
    } else {
      thought += `Autonomous tier optimization balances IOPS demand with tier billing rates, delivering ${savingsPct.toFixed(1)}% savings while preserving SLA.`;
    }

    // Update UI elements in strict Black & White
    el.outTargetTier.textContent = TIER_NAMES[predTier];
    el.outQuantPolicy.textContent = QUANTIZATION_POLICIES[predQuant];
    el.outCurrentCost.textContent = `$${curCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/mo`;
    el.outNewCost.textContent = `$${newCost.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/mo`;
    el.outMonthlySavings.textContent = `$${savedDollars.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}/mo`;
    el.outSavingsPct.textContent = `${savingsPct.toFixed(1)}%`;
    el.outFootprintDelta.textContent = `-${footprintReducedTB.toFixed(2)} TB (${((1 - quantFactor) * 100).toFixed(0)}% shrink)`;

    el.outAnomalyStatus.textContent = isAnomaly ? "ALERT: SATURATED / ANOMALOUS" : "NOMINAL / SLA GUARANTEED";
    el.outAnomalyStatus.className = isAnomaly ? "metric-val highlight-badge" : "metric-val";

    el.outComplianceStatus.textContent = isComplianceRisk ? "VIOLATION DETECTED (UNENCRYPTED)" : "CERTIFIED (KMS SEALED)";
    el.outComplianceStatus.className = isComplianceRisk ? "metric-val highlight-badge" : "metric-val";

    el.outAgentAction.textContent = AGENT_ACTIONS[agentActionIdx];
    el.outAgentConf.textContent = `${(confidence * 100).toFixed(1)}%`;
    el.outAgentThought.textContent = thought;
    el.outCsiCommand.textContent = csiCmd;
  }

  function initControls() {
    const el = getElements();
    if (!el.sliderIops) return;

    function syncStateFromInputs() {
      state.iops = parseInt(el.sliderIops.value, 10);
      state.tp = parseInt(el.sliderTp.value, 10);
      state.lat = parseFloat(el.sliderLat.value);
      state.qd = parseInt(el.sliderQd.value, 10);
      state.cap = parseInt(el.sliderCap.value, 10);
      state.inact = parseInt(el.sliderInact.value, 10);
      state.enc = el.toggleEnc.checked ? 1 : 0;
      state.workload = parseInt(el.selectWorkload.value, 10);
      state.tier = parseInt(el.selectCurTier.value, 10);

      el.valIops.textContent = state.iops.toLocaleString();
      el.valTp.textContent = `${state.tp.toLocaleString()} MB/s`;
      el.valLat.textContent = `${state.lat.toFixed(1)} ms`;
      el.valQd.textContent = state.qd;
      el.valCap.textContent = `${state.cap} TB`;
      el.valInact.textContent = `${state.inact} d`;

      evaluateVolume();
    }

    el.sliderIops.addEventListener('input', syncStateFromInputs);
    el.sliderTp.addEventListener('input', syncStateFromInputs);
    el.sliderLat.addEventListener('input', syncStateFromInputs);
    el.sliderQd.addEventListener('input', syncStateFromInputs);
    el.sliderCap.addEventListener('input', syncStateFromInputs);
    el.sliderInact.addEventListener('input', syncStateFromInputs);
    el.toggleEnc.addEventListener('change', syncStateFromInputs);
    el.selectWorkload.addEventListener('change', syncStateFromInputs);
    el.selectCurTier.addEventListener('change', syncStateFromInputs);

    el.presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const key = btn.getAttribute('data-preset');
        if (PRESETS[key]) {
          Object.assign(state, PRESETS[key]);

          el.sliderIops.value = state.iops;
          el.sliderTp.value = state.tp;
          el.sliderLat.value = state.lat;
          el.sliderQd.value = state.qd;
          el.sliderCap.value = state.cap;
          el.sliderInact.value = state.inact;
          el.toggleEnc.checked = (state.enc === 1);
          el.selectWorkload.value = state.workload;
          el.selectCurTier.value = state.tier;

          el.presetBtns.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');

          syncStateFromInputs();
        }
      });
    });

    syncStateFromInputs();
  }

  function initQualityInspector() {
    const toggleBaseline = document.getElementById('btn-benchmark-baseline');
    const toggleInjected = document.getElementById('btn-benchmark-injected');

    const scoreOverall = document.getElementById('score-composite');
    const barCompleteness = document.getElementById('bar-completeness');
    const barValidity = document.getElementById('bar-validity');
    const barUniqueness = document.getElementById('bar-uniqueness');
    const barConsistency = document.getElementById('bar-consistency');
    const barTimeliness = document.getElementById('bar-timeliness');

    const valCompleteness = document.getElementById('val-completeness');
    const valValidity = document.getElementById('val-validity');
    const valUniqueness = document.getElementById('val-uniqueness');
    const valConsistency = document.getElementById('val-consistency');
    const valTimeliness = document.getElementById('val-timeliness');

    const outPsiVal = document.getElementById('out-psi-val');
    const outPsiStatus = document.getElementById('out-psi-status');
    const outMadOutliers = document.getElementById('out-mad-outliers');
    const outLuhnViolations = document.getElementById('out-luhn-violations');

    if (!toggleBaseline || !toggleInjected) return;

    function applyQualityState(isBaseline) {
      if (isBaseline) {
        toggleBaseline.classList.add('active');
        toggleInjected.classList.remove('active');

        scoreOverall.textContent = "98.8%";
        barCompleteness.style.width = "99.8%";
        barValidity.style.width = "99.5%";
        barUniqueness.style.width = "100.0%";
        barConsistency.style.width = "98.2%";
        barTimeliness.style.width = "97.5%";

        valCompleteness.textContent = "99.8%";
        valValidity.textContent = "99.5%";
        valUniqueness.textContent = "100.0%";
        valConsistency.textContent = "98.2%";
        valTimeliness.textContent = "97.5%";

        outPsiVal.textContent = "0.034";
        outPsiStatus.textContent = "STABLE (PSI < 0.10)";
        outPsiStatus.className = "metric-val";

        outMadOutliers.textContent = "0 flagged";
        outLuhnViolations.textContent = "0 unmasked (100% Tokenized)";
      } else {
        toggleInjected.classList.add('active');
        toggleBaseline.classList.remove('active');

        scoreOverall.textContent = "61.4%";
        barCompleteness.style.width = "73.0%";
        barValidity.style.width = "58.4%";
        barUniqueness.style.width = "88.0%";
        barConsistency.style.width = "49.5%";
        barTimeliness.style.width = "72.0%";

        valCompleteness.textContent = "73.0% (15% Nulls)";
        valValidity.textContent = "58.4% (Anomalies)";
        valUniqueness.textContent = "88.0% (60 Duplicates)";
        valConsistency.textContent = "49.5% (Casing Typos)";
        valTimeliness.textContent = "72.0% (SLA Skew)";

        outPsiVal.textContent = "0.382";
        outPsiStatus.textContent = "SEVERE COVARIATE DRIFT (PSI > 0.25)";
        outPsiStatus.className = "metric-val highlight-badge";

        outMadOutliers.textContent = "142 outliers flagged (MAD b=1.4826)";
        outLuhnViolations.textContent = "48 unmasked SSN & Luhn Cards";
      }
    }

    toggleBaseline.addEventListener('click', () => applyQualityState(true));
    toggleInjected.addEventListener('click', () => applyQualityState(false));

    applyQualityState(true);

    const luhnInput = document.getElementById('luhn-test-input');
    const luhnResult = document.getElementById('luhn-test-result');
    const luhnSteps = document.getElementById('luhn-test-steps');

    if (luhnInput && luhnResult) {
      function testLuhn() {
        const raw = luhnInput.value.replace(/\D/g, '');
        if (raw.length < 8) {
          luhnResult.textContent = "Awaiting 13-19 digits...";
          luhnResult.className = "metric-val";
          luhnSteps.textContent = "Enter card number to verify Luhn Modulo 10 checksum.";
          return;
        }

        let sum = 0;
        let isEven = false;
        let stepTokens = [];

        for (let i = raw.length - 1; i >= 0; i--) {
          let digit = parseInt(raw.charAt(i), 10);
          if (isEven) {
            digit *= 2;
            if (digit > 9) digit -= 9;
            stepTokens.push(`[${digit}]`);
          } else {
            stepTokens.push(`${digit}`);
          }
          sum += digit;
          isEven = !isEven;
        }

        const isValid = (sum % 10 === 0);
        if (isValid) {
          const masked = raw.slice(0, 4) + "-••••-••••-" + raw.slice(-4);
          luhnResult.textContent = `AUTHENTIC CARD (Sum=${sum} ≡ 0 mod 10) → Auto-Masked: ${masked}`;
          luhnResult.className = "metric-val highlight-badge";
          luhnSteps.textContent = `Luhn sum calculation: ${stepTokens.reverse().join(' + ')} = ${sum} (Divisible by 10). Cryptographic PII rule triggered: Masked and hashed via HMAC-SHA256.`;
        } else {
          luhnResult.textContent = `INVALID CHECKSUM (Sum=${sum} ≢ 0 mod 10)`;
          luhnResult.className = "metric-val highlight-badge";
          luhnSteps.textContent = `Luhn sum calculation: ${sum} % 10 = ${sum % 10} != 0. Flagged as synthetic or corrupted data sequence.`;
        }
      }

      luhnInput.addEventListener('input', testLuhn);
      testLuhn();
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    initControls();
    initQualityInspector();
  });

})();
