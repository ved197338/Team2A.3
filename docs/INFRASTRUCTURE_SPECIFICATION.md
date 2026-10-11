# Innov8OptNet: Infrastructure Layer Specification
### Kubernetes CSI Auto-Tiering, Storage Policy Engine & Multi-Tier Backend Integration

---

## 1. Scope & Role of the Infrastructure Layer

As defined in the Domain 2A project specification:
> **Infrastructure:** *"Integration with S3, Ceph, NetApp and Pure via a policy engine and Kubernetes CSI; auto-tiering controller."*

The Infrastructure Layer serves as the **deterministic execution bridge** between abstract neural model outputs and physical cloud storage hardware.

---

## 2. Multi-Storage Backend Integration Matrix

| Storage Backend | Architecture Tier | Protocols Supported | Production Workload Assignment |
| :--- | :--- | :--- | :--- |
| **Ceph Storage (RBD / CephFS)** | Hot NVMe & Warm SSD | Block (RBD), File (CephFS) | High-performance Kubernetes volumes, AI training datasets |
| **Pure Storage (FlashArray)** | Hot NVMe Tier | NVMe-oF, iSCSI | Sub-millisecond transactional OLTP databases |
| **NetApp (ONTAP)** | Warm SSD Tier | NFS, iSCSI, SMB | General-purpose microservices and build artifact stores |
| **Amazon S3 / S3 Glacier** | Cold & Deep Archive | REST S3 API, Glacier Vault | Regulatory compliance archives (7-10 year retention) |
| **Local Host Workstation** | Physical NVMe / SATA | POSIX (`/dev/nvme0n1p2`) | Local developer workspaces, code repositories, logs |

---

## 3. Kubernetes CSI Auto-Tiering Controller

### 3.1 Container Storage Interface (CSI) Overview
The **Container Storage Interface (CSI)** is an industry-standard gRPC API specification that enables container orchestrators like Kubernetes to interact with heterogeneous storage vendor hardware without requiring vendor-specific code in the Kubernetes core.

### 3.2 Dynamic StorageClass Rebinding
When the AI detects volume underutilization or temperature shifts, the Auto-Tiering Controller issues standard declarative patch commands:
```bash
kubectl patch pvc <pvc-name> -p '{"spec":{"storageClassName":"warm-ssd-sc"}}'
```

### 3.3 Zero-Data-Loss VolumeSnapshotClass Protocol
To prevent data corruption during tier migration, our controller executes an automated snapshot prior to migration:
```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: pre-tiering-snapshot
spec:
  volumeSnapshotClassName: csi-rbd-snapclass
  source:
    persistentVolumeClaimName: production-pvc
```

---

## 4. The Storage Policy Engine (`StorageSandboxExecutor`)

The Policy Engine converts neural logits into viable, verified Linux terminal commands:

1. **Compression Directives:**
   ```bash
   zstd -19 --threads=4 /data/logs/db_archive.log -o /data/logs/db_archive.log.zst
   ```
2. **Kernel Read-Ahead Elevator Tuning:**
   ```bash
   blockdev --setra 8192 /dev/nvme0n1p2
   ```
3. **Dynamic INT8 Quantization:**
   Executes PyTorch post-training static and dynamic quantization on neural model weights, reducing footprint by 75% while maintaining accuracy.

---

## 5. Non-Destructive Sandbox Safety Rails

1. **Syntax Pre-Flight Verification**: Every generated bash/python command is parsed and tested in an isolated dry-run Linux namespace.
2. **Zero-Deletion Guarantee**: The engine applies lossless compression (Zstandard, Gzip, PKZIP) and volume tier migration, but **never executes destructive file removals (`rm -rf`)**.
3. **Exit Code Verification**: Commands are only committed to production when the sandbox returns exit code `0`.
