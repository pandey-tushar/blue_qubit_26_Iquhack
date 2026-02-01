#!/usr/bin/env python3
"""
Run solve_circuit.py for all P1-P10 circuits and save results.

P6 special-case (verified): do NOT use PyZX; use Qiskit approximation_degree=0.99.

Usage:
    python run_all.py
    python run_all.py --qasm-dir ./challenge
    python run_all.py --circuits P9 P10
"""

import argparse
import json
import time
from pathlib import Path

from solve_circuit import solve


CIRCUITS = {
    "P1": "P1_little_peak.qasm",
    "P2": "P2_small_bump.qasm",
    "P3": "P3_tiny_ripple.qasm",
    "P4": "P4_gentle_mound.qasm",
    "P5": "P5_soft_rise.qasm",
    "P6": "P6_low_hill.qasm",
    "P7": "P7_rolling_ridge.qasm",
    "P8": "P8_bold_peak.qasm",
    "P9": "P9_grand_summit.qasm",
    "P10": "P10_eternal_mountain.qasm",
}

# Circuit-specific overrides
CIRCUIT_OVERRIDES = {
    # P6 collapses extremely well via approximate transpilation.
    "P6": {"skip_pyzx": True, "approx_degree": 0.99},
}


def run_all(
    qasm_dir: str = ".",
    circuits: list[str] | None = None,
    shots: int = 2000,
    bond_dim: int = 128,
    strategy: str = "clifford_simp",
    output_dir: str = "results",
) -> dict:
    qasm_dir_p = Path(qasm_dir)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(exist_ok=True)

    if circuits is None:
        circuits = list(CIRCUITS.keys())

    results: dict = {}
    total_start = time.perf_counter()

    print("\n" + "=" * 70)
    print("SOLVING ALL CIRCUITS")
    print(f"Circuits: {', '.join(circuits)}")
    print(f"Default strategy: {strategy}, bond_dim={bond_dim}, shots={shots}")
    print("=" * 70)

    for name in circuits:
        if name not in CIRCUITS:
            print(f"\nWARNING: Unknown circuit {name}, skipping")
            continue

        qasm_file = qasm_dir_p / CIRCUITS[name]
        if not qasm_file.exists():
            print(f"\nWARNING: {qasm_file} not found, skipping")
            continue

        overrides = CIRCUIT_OVERRIDES.get(name, {})
        skip_pyzx = overrides.get("skip_pyzx", False)
        approx_degree = overrides.get("approx_degree", None)

        if overrides:
            print(f"\n  [Note: Using overrides for {name}: {overrides}]")

        try:
            result = solve(
                str(qasm_file),
                shots=shots,
                bond_dim=bond_dim,
                strategy=strategy,
                skip_pyzx=skip_pyzx,
                approx_degree=approx_degree,
            )
            results[name] = result

            # Save individual result
            result_file = output_dir_p / f"{name}_result.json"
            with open(result_file, "w") as f:
                json.dump(result, f, indent=2)

        except Exception as e:
            print(f"\nERROR solving {name}: {e}")
            results[name] = {"error": str(e)}

    total_time = time.perf_counter() - total_start

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total time: {total_time:.2f}s\n")

    print(f"{'Circuit':<6} {'Qubits':<6} {'Bitstring':<72} {'Count':<18}")
    print("-" * 110)

    for name in circuits:
        r = results.get(name)
        if not r:
            continue
        if "bitstring" in r:
            bs = r["bitstring"]
            qubits = len(bs)
            count_str = f"{r['count']}/{r['total_shots']} ({100*r['count']/r['total_shots']:.1f}%)"
            print(f"{name:<6} {qubits:<6} {bs:<72} {count_str:<18}")
        else:
            print(f"{name:<6} ERROR: {r.get('error', 'Unknown error')}")

    # Save combined results
    combined_file = output_dir_p / "all_results.json"
    with open(combined_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {output_dir_p}/")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run solver on all P1-P10 circuits")
    parser.add_argument("--qasm-dir", default=".", help="Directory containing QASM files")
    parser.add_argument("--circuits", nargs="+", help="Specific circuits to run (e.g., P9 P10)")
    parser.add_argument("--shots", type=int, default=2000, help="Number of shots")
    parser.add_argument("--bond-dim", type=int, default=128, help="MPS bond dimension")
    parser.add_argument(
        "--strategy",
        default="clifford_simp",
        choices=["clifford_simp", "full_reduce", "spider_simp"],
        help="Default PyZX simplification strategy",
    )
    parser.add_argument("--output-dir", default="results", help="Output directory for results")
    args = parser.parse_args()

    run_all(
        qasm_dir=args.qasm_dir,
        circuits=args.circuits,
        shots=args.shots,
        bond_dim=args.bond_dim,
        strategy=args.strategy,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

