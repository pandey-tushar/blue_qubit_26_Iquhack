"""
Circuit solver using PyZX + Qiskit optimization + MPS simulation.

Pipeline:
1. Load QASM
2. (Optional) PyZX simplify
3. Qiskit transpiler optimization (level 3, optional approximation)
4. MPS sampling (Qiskit-Aer)

Important correctness details:
- Add measurements BEFORE transpile (critical for stable results)
- Use PyZX extract_circuit() without forcing up_to_perm=False
"""

import json
import time

import pyzx as zx
from qiskit import QuantumCircuit, transpile, qasm2
from qiskit_aer import AerSimulator


def load_qasm(path: str) -> str:
    """Load QASM file and remove barrier lines."""
    with open(path, "r") as f:
        qasm_str = f.read()
    # Remove barriers (PyZX doesn't like them)
    qasm_str = "\n".join(
        line for line in qasm_str.split("\n") if not line.strip().startswith("barrier")
    )
    return qasm_str


def pyzx_simplify(qasm_str: str, strategy: str = "clifford_simp") -> str:
    """
    Apply PyZX simplification.

    Strategies:
    - 'clifford_simp': usually robust, often simplifies well
    - 'full_reduce': aggressive ZX-calculus reduction
    - 'spider_simp': similar family to clifford_simp
    - 'teleport_reduce': teleportation-based reduction
    """
    circuit = zx.Circuit.from_qasm(qasm_str)
    print(f"  Original: {circuit.qubits} qubits, {len(circuit.gates)} gates")

    g = circuit.to_graph()

    if strategy == "clifford_simp":
        zx.simplify.clifford_simp(g)
    elif strategy == "spider_simp":
        zx.simplify.spider_simp(g)
    elif strategy == "full_reduce":
        zx.full_reduce(g)
    elif strategy == "teleport_reduce":
        zx.teleport_reduce(g)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    # IMPORTANT: do NOT force up_to_perm=False
    circ_reduced = zx.extract_circuit(g)
    print(f"  After {strategy}: {len(circ_reduced.gates)} gates")

    return circ_reduced.to_qasm()


def qiskit_optimize(
    qasm_str: str,
    optimization_level: int = 3,
    approximation_degree: float | None = None,
) -> QuantumCircuit:
    """Apply Qiskit transpiler optimization."""
    qc = QuantumCircuit.from_qasm_str(qasm_str)
    print(f"  Before transpile: depth={qc.depth()}, size={qc.size()}")

    # CRITICAL: measure before transpile
    qc.measure_all()

    optimized = transpile(
        qc,
        basis_gates=["u3", "cx"],
        optimization_level=optimization_level,
        approximation_degree=approximation_degree,
    )

    approx_str = f", approx={approximation_degree}" if approximation_degree else ""
    print(
        f"  After transpile (level {optimization_level}{approx_str}): "
        f"depth={optimized.depth()}, size={optimized.size()}"
    )
    return optimized


def run_mps(qc: QuantumCircuit, shots: int = 2000, bond_dim: int = 128) -> dict[str, int]:
    """Run simulation using Qiskit Aer MPS backend."""
    backend = AerSimulator(method="matrix_product_state")
    backend.set_options(matrix_product_state_max_bond_dimension=bond_dim)

    print(f"  MPS backend: CPU, bond_dim={bond_dim}")

    t0 = time.perf_counter()
    job = backend.run(qc, shots=shots)
    counts = job.result().get_counts()
    dt = time.perf_counter() - t0
    print(f"  Sample time: {dt:.2f}s")

    return counts


def reconstruct_bitstring(measurement: str, n_qubits: int) -> str:
    """
    Normalize Aer count keys to a clean bitstring.

    - Removes spaces (Aer may insert spaces for readability on large bitstrings)
    - Truncates to n_qubits bits (defensive; should already match)
    """
    measurement = measurement.replace(" ", "")
    if len(measurement) > n_qubits:
        measurement = measurement[:n_qubits]
    return measurement


def solve(
    qasm_path: str,
    shots: int = 2000,
    bond_dim: int = 128,
    strategy: str = "clifford_simp",
    opt_level: int = 3,
    approx_degree: float | None = None,
    skip_pyzx: bool = False,
) -> dict:
    """Solve a circuit to find its peak bitstring."""
    print(f"\n{'='*60}")
    print(f"Solving: {qasm_path}")
    approx_str = f", approx={approx_degree}" if approx_degree else ""
    pyzx_str = " (skip PyZX)" if skip_pyzx else f", strategy={strategy}"
    print(f"bond_dim={bond_dim}, shots={shots}{approx_str}{pyzx_str}")
    print(f"{'='*60}")

    t_start = time.perf_counter()

    print("\n[1] Loading QASM...")
    _ = load_qasm(qasm_path)  # keeps barrier stripping behavior explicit

    # Re-dump through Qiskit for a clean canonical QASM string
    qc_orig = QuantumCircuit.from_qasm_file(qasm_path)
    qasm_str = qasm2.dumps(qc_orig)
    n_qubits = qc_orig.num_qubits
    print(
        f"  Loaded: {qc_orig.num_qubits} qubits, depth={qc_orig.depth()}, size={qc_orig.size()}"
    )

    if skip_pyzx:
        print("\n[2] Skipping PyZX (using Qiskit transpile only)...")
        qasm_opt = qasm_str
    else:
        print(f"\n[2] PyZX Simplification ({strategy})...")
        try:
            qasm_opt = pyzx_simplify(qasm_str, strategy=strategy)
        except Exception as e:
            print(f"  PyZX failed: {e}")
            print("  Falling back to original circuit...")
            qasm_opt = qasm_str

    print(f"\n[3] Qiskit Transpile (level {opt_level})...")
    qc = qiskit_optimize(
        qasm_opt, optimization_level=opt_level, approximation_degree=approx_degree
    )

    print("\n[4] MPS Simulation...")
    counts = run_mps(qc, shots=shots, bond_dim=bond_dim)

    peak_raw = max(counts, key=counts.get)
    peak_count = counts[peak_raw]
    peak_bitstring = reconstruct_bitstring(peak_raw, n_qubits)

    dt_total = time.perf_counter() - t_start

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total time: {dt_total:.2f}s")
    print(f"\nPeak bitstring: {peak_bitstring}")
    print(f"Count: {peak_count}/{shots} ({100*peak_count/shots:.1f}%)")

    print("\nTop 5:")
    for bs, c in sorted(counts.items(), key=lambda x: -x[1])[:5]:
        reconstructed = reconstruct_bitstring(bs, n_qubits)
        print(f"  {reconstructed}: count={c}")

    return {
        "bitstring": peak_bitstring,
        "count": peak_count,
        "total_shots": shots,
        "time": dt_total,
        "strategy": strategy,
        "bond_dim": bond_dim,
        "skip_pyzx": skip_pyzx,
        "approx_degree": approx_degree,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Solve circuit using PyZX + MPS")
    parser.add_argument("qasm", help="Path to QASM file")
    parser.add_argument("--shots", type=int, default=2000, help="Number of shots")
    parser.add_argument("--bond-dim", type=int, default=128, help="MPS bond dimension")
    parser.add_argument(
        "--strategy",
        choices=["clifford_simp", "full_reduce", "spider_simp", "teleport_reduce"],
        default="clifford_simp",
        help="PyZX simplification strategy",
    )
    parser.add_argument("--opt-level", type=int, default=3, help="Qiskit optimization level")
    parser.add_argument(
        "--approx-degree",
        type=float,
        default=None,
        help="Qiskit approximation degree (0.0-1.0)",
    )
    parser.add_argument("--skip-pyzx", action="store_true", help="Skip PyZX simplification")
    parser.add_argument("--output", help="Output JSON file for results")
    args = parser.parse_args()

    result = solve(
        args.qasm,
        shots=args.shots,
        bond_dim=args.bond_dim,
        strategy=args.strategy,
        opt_level=args.opt_level,
        approx_degree=args.approx_degree,
        skip_pyzx=args.skip_pyzx,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()

