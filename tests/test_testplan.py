from pathlib import Path

import pytest

from bench.testplan import SweepAxis, TestPlanError, load_testplan

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_PLAN = REPO_ROOT / "testplans" / "smoke.yaml"


def write_plan(tmp_path, text):
    path = tmp_path / "plan.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_smoke_plan_loads():
    plan = load_testplan(SMOKE_PLAN)
    assert plan.name == "smoke"
    assert [c.id for c in plan.campaigns] == ["shmoo_rp2040_coarse", "crc_soak"]

    shmoo = plan.campaigns[0]
    assert shmoo.workload == "march"
    assert shmoo.spec_ref
    assert shmoo.pass_criterion
    assert shmoo.grid["core_mv"].values() == [850, 1000, 1150, 1300]
    assert shmoo.grid["sys_clk_mhz"].values() == [125, 175, 225, 275]
    assert len(shmoo.grid_points()) == 16
    assert shmoo.grid_points()[0] == {"core_mv": 850, "sys_clk_mhz": 125}

    soak = plan.campaigns[1]
    assert soak.params == {"cycles": 100}
    assert soak.grid_points() == []


def test_sweep_axis_values_avoid_float_drift():
    axis = SweepAxis(start=0.85, stop=1.30, step=0.05)
    values = axis.values()
    assert len(values) == 10
    assert values[0] == pytest.approx(0.85)
    assert values[-1] == pytest.approx(1.30)


def test_missing_pass_criterion_rejected(tmp_path):
    path = write_plan(
        tmp_path,
        """
name: bad
campaigns:
  - id: x
    workload: march
    spec_ref: "some spec"
""",
    )
    with pytest.raises(TestPlanError, match="pass_criterion"):
        load_testplan(path)


def test_missing_spec_ref_rejected(tmp_path):
    path = write_plan(
        tmp_path,
        """
name: bad
campaigns:
  - id: x
    workload: march
    pass_criterion: "passes"
""",
    )
    with pytest.raises(TestPlanError, match="spec_ref"):
        load_testplan(path)


def test_duplicate_campaign_ids_rejected(tmp_path):
    path = write_plan(
        tmp_path,
        """
name: bad
campaigns:
  - {id: x, workload: march, spec_ref: s, pass_criterion: p}
  - {id: x, workload: crc, spec_ref: s, pass_criterion: p}
""",
    )
    with pytest.raises(TestPlanError, match="duplicate"):
        load_testplan(path)


def test_bad_step_rejected(tmp_path):
    path = write_plan(
        tmp_path,
        """
name: bad
campaigns:
  - id: x
    workload: march
    spec_ref: s
    pass_criterion: p
    grid:
      mv: {start: 100, stop: 200, step: 0}
""",
    )
    with pytest.raises(TestPlanError, match="step must be positive"):
        load_testplan(path)


def test_stop_below_start_rejected(tmp_path):
    path = write_plan(
        tmp_path,
        """
name: bad
campaigns:
  - id: x
    workload: march
    spec_ref: s
    pass_criterion: p
    grid:
      mv: {start: 200, stop: 100, step: 10}
""",
    )
    with pytest.raises(TestPlanError, match="below start"):
        load_testplan(path)


def test_empty_campaign_list_rejected(tmp_path):
    path = write_plan(tmp_path, "name: bad\ncampaigns: []\n")
    with pytest.raises(TestPlanError, match="non-empty"):
        load_testplan(path)


def test_non_mapping_top_level_rejected(tmp_path):
    path = write_plan(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(TestPlanError, match="top level"):
        load_testplan(path)
