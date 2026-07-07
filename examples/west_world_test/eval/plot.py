"""Plot recorder accuracy over ticks from JSONL comparison results."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="examples/west_world_test/results.jsonl")
    parser.add_argument("--out", default="examples/west_world_test/drift_curve.png")
    args = parser.parse_args()
    grouped = defaultdict(lambda: defaultdict(list))
    with open(args.results, encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)
            grouped[record["method"]][record["tick"]].append(bool(record["correct"]))
    plt.figure(figsize=(7, 4))
    for method, by_tick in grouped.items():
        ticks = sorted(by_tick)
        plt.plot(ticks, [sum(by_tick[tick]) / len(by_tick[tick]) for tick in ticks], marker="o", label=method)
    plt.xlabel("tick")
    plt.ylabel("probe accuracy")
    plt.ylim(0, 1.05)
    plt.title("Recorder drift: accuracy over ticks")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
