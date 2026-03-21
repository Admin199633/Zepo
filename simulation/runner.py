"""
ScenarioRunner — optional orchestration wrapper.

Scenarios can also be called directly as plain functions.
Runner collects results and provides a single assert_all_passed() call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi.testclient import TestClient


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    error: str = ""


class ScenarioRunner:
    def __init__(self, http: TestClient) -> None:
        self.http = http
        self.results: list[ScenarioResult] = []

    def run(self, name: str, fn: Callable[[TestClient], None]) -> ScenarioResult:
        try:
            fn(self.http)
            r = ScenarioResult(name=name, passed=True)
        except Exception as exc:
            import traceback
            r = ScenarioResult(name=name, passed=False, error=traceback.format_exc())
        self.results.append(r)
        return r

    def assert_all_passed(self) -> None:
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines = [f"\n{'='*60}\n{r.name}:\n{r.error}" for r in failures]
            raise AssertionError("Scenario failures:" + "".join(lines))
