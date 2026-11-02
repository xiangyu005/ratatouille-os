"""The MVP demo must keep running and keep telling the truth.

These tests are cheap guards against the demo rotting: they run it end to end
and check the claims it makes (disclaimer present, determinism verified by the
run itself, every section rendered).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from demo.mvp import build_report, main


def test_demo_report_renders_every_section(tmp_path: Path) -> None:
    report = asyncio.run(build_report(tmp_path / "demo.sqlite"))

    for heading in (
        "## 1. 世界與演員",
        "## 2. 同一工作集，五個排程策略",
        "## 3. 世界層走一遍",
        "## 4. 存檔與讀檔",
        "## 5. 決定性",
        "## 6. 效能",
        "## 7. 這個 MVP 的邊界",
        "## 8. 報告骨架",
    ):
        assert heading in report, heading

    # sample values must stay labelled as assumptions
    assert "示範假設" in report
    assert "不是遊戲規格" in report


def test_demo_world_run_is_deterministic(tmp_path: Path) -> None:
    report = asyncio.run(build_report(tmp_path / "demo.sqlite"))

    assert "| run A ↔ run B | 20 | 是 |" in report
    assert "| run A ↔ 本頁 demo | 20 | 是 |" in report


def test_demo_reports_measurable_claims(tmp_path: Path) -> None:
    report = asyncio.run(build_report(tmp_path / "demo.sqlite"))

    # idempotency, save/load and the tick budget are part of the demo's story
    assert "`cached=True`、新增事件 0 筆" in report
    assert "讀回存檔 | 4" in report
    assert "ms" in report


def test_demo_cli_writes_report(tmp_path: Path, capsys) -> None:
    out = tmp_path / "report" / "mvp.md"
    assert main(["--db", str(tmp_path / "demo.sqlite"), "--out", str(out)]) == 0

    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# 鼠於我的小餐館｜MVP 示範")
    captured = capsys.readouterr()
    assert "[demo] report written to" in captured.out
