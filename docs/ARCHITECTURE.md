# Innov8OptNet: System Architecture & Technical Specifications
### Domain 2A: Smartly Optimize Storage for Modern Workloads (HackFest 2026)
**Autonomous Multi-Tier Storage Optimization Engine with 80M Transformer Backbone**

---

## 1. System Overview

**Innov8OptNet** is an autonomous storage optimization controller designed for modern enterprise multi-tenant Kubernetes clusters and high-performance computing environments. It bridges real-time block-level I/O telemetry with deep reinforcement learning and automated Kubernetes Container Storage Interface (CSI) drivers, dynamically migrating workloads between ultra-fast NVMe, balanced SSD, high-density HDD, and deep cloud archive (Amazon S3 Glacier).

---

## 2. Four-Tier Architecture Stack

```
+---------------------------------------------------------------------------------+
|                              LAYER 1: DATA LAYER                                |
|  - Telemetry Collection: /proc/diskstats, Prometheus node_exporter, OpenTelemetry |
|  - Empirical Traces: Alibaba Cloud EBS (5,000+ volumes), SNIA IOTTA, MLPerf     |
|  - Feature Vector: 11 structured metrics per workload                           |
|  - Normalization: Scale-invariant log-Pareto transformation: f(x) = ln(1 + x)   |
+----------------------------------------┬----------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                             LAYER 2: MODELING / AI                              |
|  - Architecture: 80,003,187 parameter Pre-LN Transformer Encoder                |
|  - Hyperparameters: 6 layers, 16 attention heads, d_model = 1024, d_ff = 4196   |
|  - Sequence Tokenizer: 4-token structural sequence representation               |
|  - Multi-Task Inference: 8 simultaneous classification & regression heads       |
|  - Optimization: PPO Reinforcement Learning policy actor-critic fine-tuning     |
+----------------------------------------┬----------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                         LAYER 3: INFRASTRUCTURE LAYER                          |
|  - Kubernetes CSI Controller: Declarative dynamic StorageClass patching         |
|  - Pre-Migration Snapshot Safety: VolumeSnapshotClass automated snapshots       |
|  - Heterogeneous Fabrics: Ceph (RBD/CephFS), Pure Storage FlashArray, NetApp    |
|    ONTAP, Amazon S3 / S3 Glacier Vaults                                         |
|  - Storage Policy Engine: Linux Storage OS sandbox with non-destructive guards  |
+----------------------------------------┬----------------------------------------+
                                         |
                                         v
+---------------------------------------------------------------------------------+
|                          LAYER 4: APPLICATION LAYER                             |
|  - Web UI: Clean, borderless bold black high-contrast telemetry dashboard       |
|  - REST Microservice: Asynchronous FastAPI backend with sub-50ms CPU execution  |
|  - Multi-Format Reporting: ReportLab Platypus vector PDF and CSV export         |
|  - Dual Operational Modes: Workstation Local Storage vs. Enterprise Cluster     |
+---------------------------------------------------------------------------------+
```

---

## 3. Data Ingestion & Mathematical Transformation (Layer 1)

### 3.1 Workload Telemetry Feature Vector
Each workload $W_i$ is described by an 11-dimensional raw telemetry vector:
1. `IOPS`: Instantaneous I/O operations per second ($[0, 10^6]$).
2. `Throughput`: Instantaneous read/write data transfer rate in MB/s ($[0, 10^4]$).
3. `Latency`: Average round-trip I/O latency in milliseconds ($[0.05, 500.0]$).
4. `QueueDepth`: Storage device queue depth saturation level ($[1, 128]$).
5. `Capacity`: Allocated volume size in gigabytes ($[10, 50000]$).
6. `AccessFrequency`: Access rate per day ($[0.0, 1000.0]$).
7. `DaysInactive`: Elapsed days since last read/write operation ($[0, 365]$).
8. `SLALimit`: Contractual maximum tolerable latency in milliseconds ($[1.0, 200.0]$).
9. `Retention`: Target data retention period in years ($[1, 10]$).
10. `WorkloadType`: Categorical workload identifier ($\{0: \text{DB}, 1: \text{AI}, 2: \text{LOG}, 3: \text{APP}, 4: \text{STREAM}, 5: \text{BACKUP}\}$).
11. `CurrentTier`: Current physical storage tier ($\{0: \text{NVMe}, 1: \text{SSD}, 2: \text{HDD}, 3: \text{GLACIER}\}$).

### 3.2 Monotonic Log-Pareto Normalization
To prevent large-magnitude features (such as IOPS and Throughput) from dominating small-magnitude features (such as Latency and Queue Depth), all numerical values undergo:

$$f(x) = \log_e(1 + x)$$

This bounds the input variance, ensuring stable numerical gradient backpropagation across all layers of the 80M-parameter Transformer.

---

## 4. Deep Learning Model Topology (Layer 2)

### 4.1 Token Sequence Embeddings
The input vector is projected into a 4-token sequence of 1024-dimensional continuous representations:
- **Token 1 (Numerical Metrics)**: Linear projection of 9 normalized numerical scalars:
  $$\mathbf{z}_1 = \text{GELU}(\text{LayerNorm}(\mathbf{W}_{\text{num}} \mathbf{x}_{\text{num}} + \mathbf{b}_{\text{num}})) \in \mathbb{R}^{1024}$$
- **Token 2 (Workload Identity)**: Learned category embedding lookup:
  $$\mathbf{z}_2 = \mathbf{E}_{\text{workload}}[\text{WorkloadType}] \in \mathbb{R}^{1024}$$
- **Token 3 (Current Physical Tier)**: Learned tier embedding lookup:
  $$\mathbf{z}_3 = \mathbf{E}_{\text{tier}}[\text{CurrentTier}] \in \mathbb{R}^{1024}$$
- **Token 4 (Encryption & Compliance)**: Linear projection of binary governance flags:
  $$\mathbf{z}_4 = \text{GELU}(\text{LayerNorm}(\mathbf{W}_{\text{enc}} x_{\text{enc}} + \mathbf{b}_{\text{enc}})) \in \mathbb{R}^{1024}$$

### 4.2 Multi-Head Attention & Pre-LayerNorm Transformer Blocks
The token sequence $\mathbf{Z}^{(0)} = [\mathbf{z}_1, \mathbf{z}_2, \mathbf{z}_3, \mathbf{z}_4] + \mathbf{P}_{\text{learned}}$ passes through 6 stacked Pre-LayerNorm Transformer blocks:

$$\mathbf{Z}^{(l)\prime} = \mathbf{Z}^{(l-1)} + \text{MultiHeadAttention}(\text{LayerNorm}(\mathbf{Z}^{(l-1)}))$$
$$\mathbf{Z}^{(l)} = \mathbf{Z}^{(l)\prime} + \text{FeedForward}(\text{LayerNorm}(\mathbf{Z}^{(l)\prime}))$$

Where the feed-forward network expands from $d_{\text{model}} = 1024$ to $d_{ff} = 4196$ with GELU non-linearities.

### 4.3 Multi-Task Decision Heads
A mean-pooling operation aggregates sequence representations into a global context vector $\mathbf{h} \in \mathbb{R}^{1024}$, fed into 8 parallel output heads:
- `Tier Classification`: Softmax distribution over candidate tiers.
- `Quantization Policy`: Softmax distribution over compression strategies (None, LZ4, Dynamic INT8, Zstandard -19).
- `Anomaly Detection`: Sigmoid probability of impending latency or queue saturation.
- `Governance Risk`: Sigmoid probability of encryption or retention compliance violation.
- `Projected Savings`: Linear scalar regression estimating monthly cost savings percentage.
- `Kubernetes Action`: Softmax distribution over CSI driver operations.
- `Storage OS Directive`: Softmax distribution over Linux system directives.
- `Decision Confidence`: Calibrated Sigmoid score reflecting predictive certainty.

---

## 5. Infrastructure Layer & Storage Policy Engine (Layer 3)

### 5.1 Kubernetes CSI Auto-Tiering Controller
The Kubernetes controller executes declarative volume patching via standard CSI gRPC interfaces:
```bash
kubectl patch pvc <pvc-name> -n production -p '{"spec":{"storageClassName":"warm-ssd-sc"}}'
```

### 5.2 Pre-Migration Volume Snapshot Protocol
Before any volume is moved across physical tiers or storage fabrics, an automated VolumeSnapshot is taken:
```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: pre-tiering-snapshot-volume-42
  namespace: production
spec:
  volumeSnapshotClassName: csi-rbd-snapclass
  source:
    persistentVolumeClaimName: production-mysql-data
```

### 5.3 Multi-Backend Storage Fabric Support
- **Ceph (RBD & CephFS)**: Distributed block and file tier for general Kubernetes storage.
- **Pure Storage FlashArray**: Ultra-low-latency NVMe-oF tier for high-throughput OLTP workloads.
- **NetApp ONTAP**: Enterprise NFS/iSCSI tier for balanced microservice applications.
- **Amazon S3 / S3 Glacier**: Scalable object tier with lifecycle vaults for archival compliance.

---

## 6. Application Layer & Telemetry Dashboard (Layer 4)

- **FastAPI Microservice**: High-throughput asynchronous backend serving `/api/predict`, `/api/simulate/batch`, `/api/sandbox/execute`, and `/api/report/pdf`.
- **UI Design System**: Clean, borderless bold black styling with zero line dividers or emojis.
- **Automated Reporting**: Programmatic vector PDF generation using ReportLab Platypus, incorporating empirical tables, telemetry distributions, and executive summaries.
