# High-Performance Computing Data Transfer Methodologies: A Technical Analysis

**Author:** Harshitha  
**Institution:** Texas Advanced Computing Center (TACC)  
**Date:** March 25, 2026  
**System:** Stampede3 HPC Cluster

---

## Abstract

This technical report presents a comprehensive analysis of data transfer methodologies for High-Performance Computing (HPC) environments, specifically focusing on heterogeneous storage system integration between local workstations and TACC's Stampede3 supercomputer. We evaluate protocol-level performance characteristics, fault tolerance mechanisms, and optimal strategies for large-scale scientific dataset migration in distributed computing workflows.

---

## 1. Introduction

### 1.1 Problem Statement

Modern computational research necessitates efficient data mobility between edge devices (workstations, external storage arrays) and centralized HPC resources. The Cotton Dataset transfer workflow exemplifies challenges inherent in cross-platform data migration:

- **Filesystem Heterogeneity:** macOS HFS+/APFS → Linux Lustre parallel filesystem
- **Network Topology Complexity:** Multi-hop traversal through institutional firewalls
- **Data Integrity Assurance:** Verification mechanisms for petabyte-scale transfers
- **Authentication Barriers:** Multi-factor authentication (MFA) integration

### 1.2 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA TRANSFER ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────────┐    │
│  │   SOURCE     │         │   NETWORK    │         │   DESTINATION    │    │
│  │   SYSTEM     │         │   LAYER      │         │   SYSTEM         │    │
│  ├──────────────┤         ├──────────────┤         ├──────────────────┤    │
│  │ macOS        │   SSH   │ Internet/    │  SSH    │ Stampede3        │    │
│  │ Workstation  │◄───────►│ TACC Network │◄───────►│ Login Nodes      │    │
│  │              │  TCP/22 │ Infrastructure│ TCP/22 │                  │    │
│  ├──────────────┤         ├──────────────┤         ├──────────────────┤    │
│  │ /Volumes/T9  │         │ Firewall     │         │ /work/10904/     │    │
│  │ (External    │         │ NAT          │         │ (Lustre PFS)     │    │
│  │  SSD/HDD)    │         │ Load Balancer│         │                  │    │
│  └──────────────┘         └──────────────┘         └──────────────────┘    │
│                                                                             │
│  Filesystem: HFS+/APFS    Protocol: SSH/SCP/RSYNC   Filesystem: Lustre     │
│  Capacity: ~2TB           Bandwidth: ~100Mbps       Capacity: ~30PB        │
│  I/O: Sequential          Latency: Variable         I/O: Parallel          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Transfer Protocol Analysis

### 2.1 Secure Copy Protocol (SCP)

**Mathematical Model for Transfer Time:**

```
T_transfer = (D / B) + (RTT × N_packets) + T_auth
```

Where:
- `D` = Dataset size (bytes)
- `B` = Effective bandwidth (bytes/sec)
- `RTT` = Round-trip time (seconds)
- `N_packets` = D / MTU
- `T_auth` = Authentication overhead

**Implementation:**

```bash
scp -r -C -o "Compression=yes" \
    /Volumes/T9/ICML/* \
    user@stampede3.tacc.utexas.edu:/work/10904/user/dataset/
```

**Characteristics:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| Encryption | AES-256-CTR | Cipher negotiated at handshake |
| Compression | Optional (-C) | Effective for text, minimal for images |
| Resumability | ❌ None | Full restart required on failure |
| Parallelism | Single-stream | Bandwidth underutilization |

### 2.2 Remote Sync Protocol (RSYNC)

**Delta Transfer Algorithm:**

```
┌─────────────────────────────────────────────────────────────┐
│                 RSYNC DELTA TRANSFER MECHANISM              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SOURCE FILE                    DESTINATION FILE            │
│  ┌─────────────────┐           ┌─────────────────┐         │
│  │ Block 1 [Hash A]│           │ Block 1 [Hash A]│ ✓ Skip  │
│  │ Block 2 [Hash B]│           │ Block 2 [Hash X]│ ⟳ Sync  │
│  │ Block 3 [Hash C]│           │ Block 3 [Hash C]│ ✓ Skip  │
│  │ Block 4 [Hash D]│           │     (missing)   │ + Add   │
│  └─────────────────┘           └─────────────────┘         │
│                                                             │
│  Rolling Checksum: Adler-32 (fast) + MD5 (verification)    │
│  Block Size: Adaptive (√file_size × 8)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Optimized Implementation:**

```bash
rsync -avzh \
    --progress \
    --partial \
    --partial-dir=.rsync-partial \
    --checksum \
    --bwlimit=50000 \
    -e "ssh -T -c aes128-ctr -o Compression=no" \
    /Volumes/T9/ICML/ \
    user@stampede3.tacc.utexas.edu:/work/10904/user/dataset/
```

**Flag Analysis:**

| Flag | Function | Performance Impact |
|------|----------|-------------------|
| `-a` | Archive mode (preserves metadata) | Minimal overhead |
| `-v` | Verbose output | I/O overhead for logging |
| `-z` | Compression during transfer | CPU tradeoff vs bandwidth |
| `-h` | Human-readable sizes | Display only |
| `--progress` | Per-file progress | Minimal overhead |
| `--partial` | Keep partial files | Enables resumability |
| `--checksum` | Force checksum comparison | Significant CPU overhead |
| `--bwlimit` | Bandwidth throttling (KB/s) | Prevents network saturation |

### 2.3 Globus Transfer Service

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      GLOBUS TRANSFER ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │   Globus    │     │   Globus Cloud  │     │   TACC Globus       │   │
│  │   Connect   │◄───►│   Transfer      │◄───►│   Endpoint          │   │
│  │   Personal  │     │   Service       │     │   (Stampede3)       │   │
│  │             │     │                 │     │                     │   │
│  │  GridFTP    │     │  Task Queue     │     │  GridFTP            │   │
│  │  Client     │     │  Optimization   │     │  Server             │   │
│  │             │     │  Fault Recovery │     │                     │   │
│  └─────────────┘     └─────────────────┘     └─────────────────────┘   │
│        │                     │                        │                 │
│        ▼                     ▼                        ▼                 │
│  ┌─────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │ /Volumes/T9 │     │ OAuth 2.0 Auth  │     │ /work/10904/...     │   │
│  │ Local FS    │     │ X.509 Certs     │     │ Lustre PFS          │   │
│  └─────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                                                         │
│  Protocol: GridFTP (parallel TCP streams, striping, pipelining)        │
│  Authentication: OAuth 2.0 + X.509 proxy certificates                  │
│  Fault Tolerance: Automatic retry, checkpoint restart                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Performance Characteristics:**

```
Throughput_GridFTP = N_streams × TCP_window × (1 / RTT)
```

Where typical configurations achieve:
- `N_streams` = 4-16 parallel streams
- `TCP_window` = 64KB - 4MB (auto-tuned)
- Effective bandwidth: 500Mbps - 10Gbps

---

## 3. Lustre Parallel Filesystem Considerations

### 3.1 Stampede3 Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LUSTRE FILESYSTEM TOPOLOGY                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌───────────────┐                               │
│                         │  Metadata     │                               │
│                         │  Server (MDS) │                               │
│                         │  ┌─────────┐  │                               │
│                         │  │   MDT   │  │                               │
│                         │  └─────────┘  │                               │
│                         └───────┬───────┘                               │
│                                 │                                       │
│            ┌────────────────────┼────────────────────┐                  │
│            │                    │                    │                  │
│            ▼                    ▼                    ▼                  │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│   │  Object Storage │  │  Object Storage │  │  Object Storage │        │
│   │  Server (OSS) 1 │  │  Server (OSS) 2 │  │  Server (OSS) N │        │
│   │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │        │
│   │  │  OST 1-4  │  │  │  │  OST 5-8  │  │  │  │ OST N-N+4 │  │        │
│   │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │        │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘        │
│                                                                         │
│   Stripe Size: 1MB (default)    Stripe Count: Variable (1-32)          │
│   Total Capacity: ~30 PB        Aggregate Bandwidth: ~500 GB/s         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Stripe Optimization for Dataset Ingestion

```bash
# Set stripe parameters for large dataset directory
lfs setstripe -c 8 -S 4M "/work/10904/harshitha114488/LLM-test/Access Proposal/Cotton Dataset"

# Verify stripe configuration
lfs getstripe "/work/10904/harshitha114488/LLM-test/Access Proposal/Cotton Dataset"
```

**Stripe Parameter Selection:**

| Dataset Characteristic | Recommended Stripe Count | Stripe Size |
|------------------------|-------------------------|-------------|
| Many small files (<1MB) | 1 | 64KB |
| Medium files (1MB-1GB) | 4 | 1MB |
| Large files (>1GB) | 8-16 | 4MB |
| Streaming I/O workload | 16-32 | 4MB |

---

## 4. Implementation Workflow

### 4.1 Pre-Transfer Checklist

```bash
#!/bin/bash
# filepath: /work/10904/harshitha114488/LLM-test/Acess_HPC/scripts/pre_transfer_check.sh

# Pre-transfer validation script for HPC data migration

set -euo pipefail

DEST_DIR="/work/10904/harshitha114488/LLM-test/Access Proposal/Cotton Dataset"

echo "=== HPC Data Transfer Pre-flight Check ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# 1. Check available quota
echo "[1/5] Checking storage quota..."
lfs quota -u $USER /work/10904/harshitha114488/ 2>/dev/null || echo "Quota check unavailable"

# 2. Check available space
echo "[2/5] Checking available disk space..."
df -h /work/10904/harshitha114488/

# 3. Create destination directory with optimal striping
echo "[3/5] Creating destination directory..."
mkdir -p "$DEST_DIR"

# 4. Set stripe configuration for large files
echo "[4/5] Configuring Lustre stripe parameters..."
lfs setstripe -c 4 -S 1M "$DEST_DIR" 2>/dev/null || echo "Stripe configuration skipped"

# 5. Verify network connectivity
echo "[5/5] Network diagnostics..."
echo "Login node: $(hostname)"
echo "External connectivity: $(ping -c 1 8.8.8.8 &>/dev/null && echo 'OK' || echo 'FAILED')"

echo ""
echo "=== Pre-flight check complete ==="
```

### 4.2 Transfer Execution Script

```bash
#!/bin/bash
# filepath: /work/10904/harshitha114488/LLM-test/Acess_HPC/scripts/execute_transfer.sh

# Execute this script FROM YOUR MAC, not on Stampede3

SOURCE_PATH="/Volumes/T9/ICML"
DEST_USER="harshitha114488"
DEST_HOST="stampede3.tacc.utexas.edu"
DEST_PATH="/work/10904/harshitha114488/LLM-test/Access Proposal/Cotton Dataset"

LOG_FILE="transfer_$(date +%Y%m%d_%H%M%S).log"

echo "Starting transfer at $(date)" | tee "$LOG_FILE"
echo "Source: $SOURCE_PATH" | tee -a "$LOG_FILE"
echo "Destination: $DEST_USER@$DEST_HOST:$DEST_PATH" | tee -a "$LOG_FILE"

# Calculate source size
SOURCE_SIZE=$(du -sh "$SOURCE_PATH" | cut -f1)
echo "Source size: $SOURCE_SIZE" | tee -a "$LOG_FILE"

# Execute rsync with optimal parameters
rsync -avzh \
    --progress \
    --partial \
    --partial-dir=.rsync-partial \
    --stats \
    --human-readable \
    --log-file="$LOG_FILE" \
    -e "ssh -T -c aes128-ctr" \
    "$SOURCE_PATH/" \
    "$DEST_USER@$DEST_HOST:\"$DEST_PATH/\""

echo "Transfer completed at $(date)" | tee -a "$LOG_FILE"
```

### 4.3 Post-Transfer Validation

```bash
#!/bin/bash
# filepath: /work/10904/harshitha114488/LLM-test/Acess_HPC/scripts/post_transfer_validate.sh

# Post-transfer validation script

DATASET_DIR="/work/10904/harshitha114488/LLM-test/Access Proposal/Cotton Dataset"

echo "=== Post-Transfer Validation ==="
echo "Timestamp: $(date -Iseconds)"
echo ""

# 1. File count
echo "[1/4] File inventory..."
TOTAL_FILES=$(find "$DATASET_DIR" -type f | wc -l)
TOTAL_DIRS=$(find "$DATASET_DIR" -type d | wc -l)
echo "Total files: $TOTAL_FILES"
echo "Total directories: $TOTAL_DIRS"

# 2. Size verification
echo ""
echo "[2/4] Storage consumption..."
du -sh "$DATASET_DIR"

# 3. File type distribution
echo ""
echo "[3/4] File type distribution..."
find "$DATASET_DIR" -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -10

# 4. Permission check
echo ""
echo "[4/4] Permission verification..."
ls -la "$DATASET_DIR" | head -20

echo ""
echo "=== Validation complete ==="
```

---

## 5. Performance Benchmarks

### 5.1 Protocol Comparison Matrix

```
┌─────────────────────────────────────────────────────────────────────────┐
│              TRANSFER PROTOCOL PERFORMANCE COMPARISON                   │
├─────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│   Metric    │     SCP      │    RSYNC     │    Globus    │   bbcp      │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Throughput  │   ~50 MB/s   │   ~60 MB/s   │  ~200 MB/s   │  ~150 MB/s  │
│ (typical)   │              │              │              │             │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Resumable   │      ❌      │      ✅      │      ✅      │     ✅      │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Delta Sync  │      ❌      │      ✅      │      ❌      │     ❌      │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Parallel    │      ❌      │      ❌      │      ✅      │     ✅      │
│ Streams     │              │              │              │             │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Encryption  │   AES-256    │   AES-256    │    TLS 1.3   │  Optional   │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Setup       │    Simple    │    Simple    │   Moderate   │  Moderate   │
│ Complexity  │              │              │              │             │
├─────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Best For    │  Small,      │  Incremental │  Large,      │  Large,     │
│             │  one-time    │  backups     │  one-time    │  one-time   │
└─────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

### 5.2 Theoretical vs. Observed Throughput

```
Expected Transfer Time Formula:

T_total = T_handshake + T_auth + (Data_size / Bandwidth_effective) + T_verification

Where:
  T_handshake ≈ 3 × RTT (TCP three-way handshake)
  T_auth ≈ 2-5 seconds (MFA token verification)
  Bandwidth_effective = min(B_source, B_network, B_dest) × efficiency_factor
  efficiency_factor ≈ 0.7-0.9 (protocol overhead, congestion)

Example Calculation (10GB dataset):
  T_total = 0.1s + 3s + (10GB / 50MB/s) + 5s
  T_total ≈ 0.1 + 3 + 200 + 5 = 208.1 seconds ≈ 3.5 minutes
```

---

## 6. Security Considerations

### 6.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TACC MULTI-FACTOR AUTHENTICATION                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  Client  │───►│  SSH Server  │───►│  TACC Auth   │───►│  TOTP    │  │
│  │          │    │  (sshd)      │    │  Service     │    │  Server  │  │
│  └──────────┘    └──────────────┘    └──────────────┘    └──────────┘  │
│       │                │                    │                  │        │
│       │  1. SSH        │  2. PAM            │  3. Verify       │        │
│       │  Connect       │  Challenge         │  TOTP Token      │        │
│       │                │                    │                  │        │
│       ▼                ▼                    ▼                  ▼        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Authentication Sequence                       │  │
│  │  1. TCP connection established (port 22)                         │  │
│  │  2. SSH version exchange                                         │  │
│  │  3. Key exchange (ECDH)                                          │  │
│  │  4. Password prompt → User enters TACC password                  │  │
│  │  5. MFA prompt → User enters 6-digit TOTP code                   │  │
│  │  6. Session established                                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Data Integrity Verification

```bash
# Generate checksums before transfer (on Mac)
find /Volumes/T9/ICML -type f -exec md5 {} \; > checksums_source.md5

# Verify after transfer (on Stampede3)
md5sum -c checksums_source.md5
```

---

## 7. Troubleshooting Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TRANSFER TROUBLESHOOTING FLOWCHART                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         ┌─────────────────┐                             │
│                         │  Transfer Fails │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│                                  ▼                                      │
│                    ┌─────────────────────────┐                          │
│                    │  Connection Refused?    │                          │
│                    └───────────┬─────────────┘                          │
│                          YES   │   NO                                   │
│                    ┌───────────┴───────────┐                            │
│                    ▼                       ▼                            │
│         ┌──────────────────┐    ┌──────────────────┐                   │
│         │ Check:           │    │ Permission       │                   │
│         │ • VPN connection │    │ Denied?          │                   │
│         │ • Firewall rules │    └────────┬─────────┘                   │
│         │ • Host reachable │       YES   │   NO                        │
│         └──────────────────┘    ┌────────┴────────┐                    │
│                                 ▼                 ▼                     │
│                      ┌──────────────┐   ┌──────────────┐               │
│                      │ Verify:      │   │ Timeout?     │               │
│                      │ • Password   │   └──────┬───────┘               │
│                      │ • MFA token  │     YES  │  NO                   │
│                      │ • Username   │   ┌──────┴──────┐                │
│                      └──────────────┘   ▼             ▼                │
│                               ┌──────────────┐ ┌──────────────┐        │
│                               │ Use rsync    │ │ Check disk   │        │
│                               │ with         │ │ space/quota  │        │
│                               │ --partial    │ │ on dest      │        │
│                               └──────────────┘ └──────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Conclusions and Recommendations

### 8.1 Protocol Selection Guidelines

| Scenario | Recommended Protocol | Rationale |
|----------|---------------------|-----------|
| First-time large transfer | Globus | Parallel streams, fault tolerance |
| Incremental updates | rsync | Delta algorithm minimizes data movement |
| Quick small file transfer | scp | Simplicity, no setup overhead |
| Unreliable network | rsync --partial | Resume capability |
| Maximum throughput | Globus or bbcp | Multi-stream parallelism |

### 8.2 Best Practices Summary

1. **Always verify source data** before initiating transfer
2. **Configure Lustre striping** appropriate to file sizes
3. **Use resumable protocols** for datasets >1GB
4. **Implement checksum verification** for critical data
5. **Monitor transfer progress** and log for auditing
6. **Schedule large transfers** during off-peak hours

---

## References

1. TACC Stampede3 User Guide. Texas Advanced Computing Center. https://docs.tacc.utexas.edu/hpc/stampede3/
2. Lustre Filesystem Documentation. OpenSFS. https://www.lustre.org/documentation/
3. Globus Transfer Service. University of Chicago. https://www.globus.org/
4. Tridgell, A., & Mackerras, P. (1996). The rsync algorithm. Australian National University.
5. GridFTP Protocol Specification. Globus Alliance.

---

## Appendix A: Quick Reference Commands

```bash
# Check disk quota on Stampede3
lfs quota -u $USER /work/

# Monitor active transfers
watch -n 5 'ls -la /work/10904/harshitha114488/LLM-test/Access\ Proposal/Cotton\ Dataset/'

# Kill stuck transfer
pkill -f rsync

# Resume interrupted rsync
rsync -avzh --partial --progress SOURCE DEST
```

---

*Report generated for TACC HPC Research Documentation*
*Version 1.0 | March 2026*