"""YAML test plan loader.

Plan requirement: each test states its spec reference and pass criterion, so
``spec_ref`` and ``pass_criterion`` are mandatory on every campaign and the
loader rejects plans that omit them.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class TestPlanError(Exception):
    """Raised when a test plan file is malformed."""

    __test__ = False  # keep pytest from collecting this as a test class


@dataclass(frozen=True)
class SweepAxis:
    start: float
    stop: float
    step: float

    def values(self) -> list[float]:
        """Inclusive sweep values, computed by index to avoid float drift."""
        count = int((self.stop - self.start) / self.step + 1e-9) + 1
        return [self.start + i * self.step for i in range(count)]


@dataclass(frozen=True)
class Campaign:
    id: str
    workload: str
    spec_ref: str
    pass_criterion: str
    grid: dict[str, SweepAxis] = field(default_factory=dict)
    params: dict = field(default_factory=dict)

    def grid_points(self) -> list[dict[str, float]]:
        """Cartesian product of all sweep axes, in axis declaration order."""
        if not self.grid:
            return []
        names = list(self.grid)
        combos = itertools.product(*(self.grid[n].values() for n in names))
        return [dict(zip(names, combo, strict=True)) for combo in combos]


@dataclass(frozen=True)
class TestPlan:
    name: str
    description: str
    campaigns: tuple[Campaign, ...]


_REQUIRED_CAMPAIGN_FIELDS = ("id", "workload", "spec_ref", "pass_criterion")


def _parse_axis(campaign_id: str, name: str, raw: object) -> SweepAxis:
    where = f"campaign '{campaign_id}' grid axis '{name}'"
    if not isinstance(raw, dict):
        raise TestPlanError(f"{where}: expected a mapping with start/stop/step")
    missing = [k for k in ("start", "stop", "step") if k not in raw]
    if missing:
        raise TestPlanError(f"{where}: missing {', '.join(missing)}")
    try:
        start = float(raw["start"])
        stop = float(raw["stop"])
        step = float(raw["step"])
    except (TypeError, ValueError) as exc:
        raise TestPlanError(f"{where}: start/stop/step must be numbers") from exc
    if step <= 0:
        raise TestPlanError(f"{where}: step must be positive, got {step}")
    if stop < start:
        raise TestPlanError(f"{where}: stop ({stop}) is below start ({start})")
    return SweepAxis(start=start, stop=stop, step=step)


def _parse_campaign(raw: object, index: int) -> Campaign:
    if not isinstance(raw, dict):
        raise TestPlanError(f"campaign #{index + 1}: expected a mapping")
    campaign_id = raw.get("id", f"#{index + 1}")
    missing = [
        k for k in _REQUIRED_CAMPAIGN_FIELDS if not isinstance(raw.get(k), str) or not raw[k]
    ]
    if missing:
        raise TestPlanError(
            f"campaign '{campaign_id}': missing or empty required field(s): {', '.join(missing)}"
        )
    grid_raw = raw.get("grid", {})
    if not isinstance(grid_raw, dict):
        raise TestPlanError(f"campaign '{campaign_id}': grid must be a mapping of axes")
    grid = {name: _parse_axis(campaign_id, name, axis) for name, axis in grid_raw.items()}
    params = raw.get("params", {})
    if not isinstance(params, dict):
        raise TestPlanError(f"campaign '{campaign_id}': params must be a mapping")
    return Campaign(
        id=raw["id"],
        workload=raw["workload"],
        spec_ref=raw["spec_ref"],
        pass_criterion=raw["pass_criterion"],
        grid=grid,
        params=params,
    )


def load_testplan(path: str | Path) -> TestPlan:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TestPlanError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise TestPlanError(f"{path}: top level must be a mapping")
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise TestPlanError(f"{path}: missing or empty 'name'")
    campaigns_raw = raw.get("campaigns")
    if not isinstance(campaigns_raw, list) or not campaigns_raw:
        raise TestPlanError(f"{path}: 'campaigns' must be a non-empty list")
    campaigns = tuple(_parse_campaign(c, i) for i, c in enumerate(campaigns_raw))
    ids = [c.id for c in campaigns]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise TestPlanError(f"{path}: duplicate campaign id(s): {', '.join(sorted(duplicates))}")
    return TestPlan(
        name=name,
        description=raw.get("description", ""),
        campaigns=campaigns,
    )
