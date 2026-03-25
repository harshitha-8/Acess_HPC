# HPC Access and Data Transfer Documentation

[![TACC](https://img.shields.io/badge/HPC-TACC%20Stampede3-blue)](https://www.tacc.utexas.edu/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

This repository contains technical documentation and scripts for High-Performance Computing (HPC) data transfer methodologies, specifically designed for TACC's Stampede3 supercomputer environment.

## Repository Structure

```
Acess_HPC/
├── README.md
├── docs/
│   └── HPC_Data_Transfer_Technical_Report.md
├── scripts/
│   ├── pre_transfer_check.sh
│   ├── execute_transfer.sh
│   └── post_transfer_validate.sh
└── diagrams/
    └── architecture_overview.md
```

## Quick Start

### Prerequisites
- TACC account with active allocation
- SSH client with MFA support
- Source data accessible on local system

### Usage

1. **Run pre-transfer checks on Stampede3:**
   ```bash
   ./scripts/pre_transfer_check.sh
   ```

2. **Execute transfer from local machine:**
   ```bash
   ./scripts/execute_transfer.sh
   ```

3. **Validate transfer on Stampede3:**
   ```bash
   ./scripts/post_transfer_validate.sh
   ```

## Documentation

- [Technical Report](docs/HPC_Data_Transfer_Technical_Report.md) - Comprehensive analysis of transfer protocols

## Author

**Harshitha**  
Texas Advanced Computing Center (TACC)

## License

MIT License - See [LICENSE](LICENSE) for details.