"""Schablonboken: nyckeltal per disciplin ur schablonlexikonet.

Beloppen i det medföljande lexikonet är exempeltal (installationsdata) —
varje installation ersätter dem med egna erfarenhetstal från genomförda
projekt. Med tiden blir den egna schablonboken en av installationens
värdefullaste tillgångar: varje avslutat projekt kan kalibrera spannen.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from importlib.resources import files
from typing import Any

from .models import Benchmark, BenchmarkRange


class BenchmarkBook:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._currency = str(payload["currency"])
        self._benchmarks: dict[tuple[str, str], Benchmark] = {}
        for discipline, entries in payload["disciplines"].items():
            for benchmark_id, entry in entries.items():
                raw_range = entry["range"]
                benchmark = Benchmark(
                    benchmark_id=str(benchmark_id),
                    discipline=str(discipline),
                    unit=str(entry["unit"]),
                    label=str(entry["label"]),
                    unit_range=BenchmarkRange(
                        low=Decimal(str(raw_range["low"])),
                        normal=Decimal(str(raw_range["normal"])),
                        high=Decimal(str(raw_range["high"])),
                    ),
                )
                self._benchmarks[(benchmark.discipline, benchmark.benchmark_id)] = benchmark

    @property
    def currency(self) -> str:
        return self._currency

    def lookup(self, discipline: str, benchmark_id: str) -> Benchmark:
        benchmark = self._benchmarks.get((discipline, benchmark_id))
        if benchmark is None:
            raise ValueError(
                f"no benchmark {benchmark_id!r} in discipline {discipline!r}; "
                f"available: {sorted(bid for d, bid in self._benchmarks if d == discipline)}"
            )
        return benchmark

    def benchmarks(self, discipline: str | None = None) -> tuple[Benchmark, ...]:
        return tuple(
            benchmark
            for (d, _), benchmark in sorted(self._benchmarks.items())
            if discipline is None or d == discipline
        )


def load_benchmarks() -> BenchmarkBook:
    resource = files("crow_benchmark_pricing").joinpath("schablon_lexikon.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    return BenchmarkBook(payload)
