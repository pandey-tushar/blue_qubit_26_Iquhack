# Blue Qubit Circuit Solver - iQuHACK 2026

Fast quantum circuit peak bitstring finder using PyZX + Qiskit + MPS simulation.

## Overview

This solver finds the peak (maximum amplitude) bitstring for peaked quantum circuits. It uses:

1. **PyZX** - ZX-calculus circuit simplification (`clifford_simp` or `full_reduce`)
2. **Qiskit** - Transpiler optimization (level 3)
3. **MPS** - Matrix Product State approximate simulation (Qiskit Aer)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Solve a single circuit

```bash
python solve_circuit.py P9_grand_summit.qasm --strategy clifford_simp --shots 2000
```

Options:
- `--strategy`: PyZX simplification strategy (`clifford_simp`, `full_reduce`, `spider_simp`)
- `--shots`: Number of MPS samples (default: 2000)
- `--bond-dim`: MPS bond dimension (default: 128)
- `--skip-pyzx`: Skip PyZX entirely (Qiskit-only)
- `--approx-degree`: Qiskit `approximation_degree` (e.g. `0.99`)
- `--output`: Save results to JSON file

### Solve all circuits (P1-P10)

```bash
python run_all.py --qasm-dir ./qasm --output-dir results
```

Options:
- `--qasm-dir`: Directory containing QASM files
- `--circuits`: Specific circuits to run (e.g., `--circuits P9 P10`)
- `--strategy`: PyZX strategy
- `--shots`: Number of shots
- `--bond-dim`: MPS bond dimension

### P6 special-case (important)

P6 is handled automatically by `run_all.py` using an override:
- `skip_pyzx=True`
- `approx_degree=0.99`

This was necessary because PyZX may take a long time on P6, while approximate Qiskit
transpilation collapses it extremely well (depth ~2) and produces a very strong peak.

## Results

| Circuit | Qubits | Strategy | Peak Bitstring | Count | Time |
|---------|--------|----------|----------------|-------|------|
| P1 | 4 | clifford_simp | 1001 | - | <1s |
| P2 | 20 | clifford_simp | 11000001000100011000 | 424/2000 (21%) | 1s |
| P6 | 60 | skip_pyzx + approx=0.99 | 101000110000100000100111100010101011101001000101100010001000 | ~1990/2000 (99%+) | <1s |
| P9 | 56 | clifford_simp | 11011000111011100000101000110001010111100100000101101110 | 820/2000 (41%) | 4s |
| P10 | 56 | clifford_simp | 00111111100000110001010111111001011101100001100100010010 | 197/2000 (10%) | 5s |

## Key Insights

- **`clifford_simp` vs `full_reduce`**: `clifford_simp` often produces simpler circuits and works better for P9
- **Measure before transpile**: Critical for correct results - add measurements BEFORE Qiskit transpile
- **PyZX extract_circuit**: Don't use `up_to_perm=False` - let PyZX handle permutations naturally

## Files

- `solve_circuit.py` - Main solver script
- `run_all.py` - Batch runner for all P1-P10 circuits
- `requirements.txt` - Python dependencies
