"""MVP demo: run the real CORE pipeline and print a report-ready summary.

The demo is deliberately doc-faithful:

- every section names the document it demonstrates, so the output grows into
  the report instead of being thrown away;
- every number that is a *demo assumption* (dish work times, priorities, the
  4-task workload) is marked as such, because docs/03 §6 and docs/06-02 §二
  forbid presenting unverified values as game spec;
- the world run uses the real engine, store and event log, not a mock.

Run:

    uv run python scripts\\run_demo.py
    uv run python scripts\\run_demo.py --out demo\\out\\mvp-report.md
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import core
from core.algorithms.scheduling import SCHEDULERS, TaskSpec, run_scheduler
from core.domain.models import Command, WorldState
from core.persistence.store import Store
from core.simulation.engine import WorldEngine

# -- demo assumptions (NOT game spec) ---------------------------------------
#
# docs/11-01 defines the stages 取料 → 烹調 for one dish, but the actual work
# seconds and priorities are still undecided (docs/03 §6, docs/11). The values
# below are a demo workload, labelled as such wherever they appear.
# (dish, stage, burst_seconds, priority)
SCENARIO: tuple[tuple[str, str, int, int], ...] = (
    ("番茄湯", "取料", 4, 0),
    ("番茄湯", "烹調", 6, 0),
    ("炒飯", "取料", 3, 2),
    ("炒飯", "烹調", 8, 2),
)
DEMO_SEED = 42
PERF_SAMPLES = 20


def scenario_specs() -> list[TaskSpec]:
    """The same workload expressed for the pure scheduler layer."""
    return [
        TaskSpec(id=f"T-{index:04d}", arrival=0, burst=burst, priority=priority)
        for index, (_, _, burst, priority) in enumerate(SCENARIO, start=1)
    ]


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join("---" for _ in header) + "|")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


class Demo:
    """One scripted session over the real CORE pipeline."""

    def __init__(self, db_path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            stale = Path(str(db_path) + suffix)
            if stale.exists():
                stale.unlink()
        self.db_path = db_path
        self.store = Store(db_path)
        self.engine = WorldEngine(WorldState.new(seed=DEMO_SEED), self.store)
        self.events: list[dict[str, Any]] = []

    async def command(
        self, name: str, args: dict[str, Any], key: str
    ) -> dict[str, Any]:
        result, emitted = await self.engine.execute(
            Command(
                command=name,
                args=args,
                idempotency_key=key,
                client="demo",
                request_id=f"demo-{key}",
            )
        )
        if emitted:
            self.events.extend(event.to_dict() for event in emitted)
        return {
            "accepted": result.accepted,
            "cached": result.cached,
            "event_ids": result.event_ids,
            "state_version": result.state_version,
        }

    async def play_scenario(self) -> None:
        """The scripted session shared by the demo and the determinism check."""
        for index in range(len(SCENARIO)):
            dish, stage, burst, priority = SCENARIO[index]
            await self.command(
                "ENQUEUE_TASK",
                {
                    "name": f"{dish}-{stage}",
                    "burst_seconds": burst,
                    "priority": priority,
                },
                f"enqueue-{index + 1}",
            )
        await self.command("SCHEDULE_QUEUE", {"policy": "sjf"}, "schedule-1")
        await self.command("ADVANCE_TIME", {"seconds": 10}, "advance-1")
        await self.command("SCHEDULE_QUEUE", {"policy": "sjf"}, "schedule-2")
        await self.command("ADVANCE_TIME", {"seconds": 10}, "advance-2")


def section_world(demo: Demo) -> str:
    state = demo.engine.state
    workers = [
        [worker.id, worker.name, str(worker.status)]
        for worker in sorted(state.workers.values(), key=lambda w: w.id)
    ]
    stations = [
        [station.id, station.name, str(station.status)]
        for station in sorted(state.stations.values(), key=lambda s: s.id)
    ]
    return "\n".join(
        [
            "## 1. 世界與演員",
            "",
            (
                "依據 `docs/17` §4、`docs/21` §3。M1 的世界只有人與工作站兩種可數資源，"
                "加上單調前進的 `sim_time`。"
            ),
            "",
            _table(["worker", "名稱", "狀態"], workers),
            "",
            _table(["station", "名稱", "狀態"], stations),
            "",
            (
                f"seed = `{state.seed}`、`sim_time = {state.sim_time}`、"
                f"`state_version = {state.version}`。"
            ),
        ]
    )


def section_algorithms() -> str:
    specs = scenario_specs()
    assignable_names = {"fcfs", "sjf", "priority_aging"}
    rows: list[list[str]] = []
    trace_rows: list[list[str]] = []
    for name in SCHEDULERS:
        result = run_scheduler(name, specs)
        metrics = result.metrics
        rows.append(
            [
                result.algorithm,
                f"`{name}`",
                "是" if name in assignable_names else "否",
                " → ".join(result.order),
                f"{metrics['makespan']:.0f}",
                f"{metrics['avg_waiting']:.2f}",
                f"{metrics['avg_turnaround']:.2f}",
                f"{metrics['cpu_utilization']:.0%}",
            ]
        )
        if name == "sjf":
            for step in result.to_dict()["trace"][:3]:
                trace_rows.append(
                    [
                        str(step["step"]),
                        str(step["input"]["time"]),
                        json.dumps(step["input"]["ready"], ensure_ascii=False),
                        str(step["output"]["selected"]),
                    ]
                )
    return "\n".join(
        [
            "## 2. 同一工作集，五個排程策略",
            "",
            (
                "依據 `docs/21` §2、`docs/03` §2。同一份 `TaskSpec` 餵給全部策略，"
                "因此差異只來自策略本身。"
            ),
            "",
            (
                "> 工作集是**示範負載**（4 件工作、秒數與優先權為假設值），不是遊戲"
                "規格。遊戲的工作耗時仍待 `11` 定案。"
            ),
            "",
            _table(
                [
                    "策略",
                    "key",
                    "可驅動世界指派",
                    "選取順序",
                    "makespan",
                    "平均等待",
                    "平均周轉",
                    "利用率",
                ],
                rows,
            ),
            "",
            (
                "`srtf`／`rr` 標「否」是刻意的：M1 的工作一旦開始就佔住 worker 與 "
                "station 到結束，搶佔式策略會和世界模型矛盾，因此只能當演算法層的"
                "比較基準（`SCHEDULE_QUEUE` 收到會回 422 `POLICY_NOT_ASSIGNABLE`）。"
            ),
            "",
            (
                "`Priority+Aging` 把優先權 2 的炒飯排在番茄湯前面，`SJF` 則照工作量"
                "排；`FCFS` 兩者都不看，只照到達順序。"
            ),
            "",
            (
                "> `cpu_utilization` 是**單一資源**的指標：工作集從 0 開始且沒有空轉，"
                "所以全部是 100%。它不代表兩人同時作業的實際產能。"
            ),
            "",
            (
                "SJF 的決策 trace（`docs/21` §5，也是未來 `schedule_tasks` Skill 的"
                "輸出格式）："
            ),
            "",
            _table(["step", "time", "ready", "selected"], trace_rows),
        ]
    )


async def section_world_run(demo: Demo) -> str:
    """Run the whole scenario through commands, then show events and Gantt."""
    enqueued: list[list[str]] = []
    for index, (dish, stage, burst, priority) in enumerate(SCENARIO, start=1):
        await demo.command(
            "ENQUEUE_TASK",
            {
                "name": f"{dish}-{stage}",
                "burst_seconds": burst,
                "priority": priority,
            },
            f"enqueue-{index}",
        )
        enqueued.append(
            [f"T-{index:04d}", f"{dish}-{stage}", str(burst), str(priority), "queued"]
        )

    await demo.command("SCHEDULE_QUEUE", {"policy": "sjf"}, "schedule-1")
    await demo.command("ADVANCE_TIME", {"seconds": 10}, "advance-1")
    await demo.command("SCHEDULE_QUEUE", {"policy": "sjf"}, "schedule-2")
    await demo.command("ADVANCE_TIME", {"seconds": 10}, "advance-2")

    # idempotency: replaying a key must not apply the command twice
    events_before = len(demo.events)
    replay = await demo.command(
        "ENQUEUE_TASK",
        {"name": "重送的工作", "burst_seconds": 9},
        "enqueue-1",
    )
    events_after = len(demo.events)

    tasks = sorted(demo.engine.state.tasks.values(), key=lambda task: task.id)
    end = max(
        (task.finished_at or 0) + 1 for task in tasks if task.finished_at is not None
    )
    gantt_rows = []
    for task in tasks:
        start = task.started_at or 0
        finish = task.finished_at if task.finished_at is not None else start
        bar = "".join("#" if start <= i < finish else "." for i in range(end))
        gantt_rows.append(
            [task.id, task.name, f"{start}→{finish}", f"`{bar}`", str(task.status)]
        )

    event_rows = [
        [
            str(event["event_id"]),
            str(event["type"]),
            str(event["sim_time"]),
            str(event["state_version"]),
        ]
        for event in demo.events[:events_before]
    ]

    return "\n".join(
        [
            "## 3. 世界層走一遍（真的 command → event）",
            "",
            (
                "依據 `docs/21` §3、`docs/22` §3.6。這一段不是模擬畫面：真的呼叫 "
                "`WorldEngine.execute`、寫入 SQLite、產生事件。"
            ),
            "",
            (
                "指令序列：`ENQUEUE_TASK` ×4 → `SCHEDULE_QUEUE(sjf)` → "
                "`ADVANCE_TIME(10)` → `SCHEDULE_QUEUE(sjf)` → `ADVANCE_TIME(10)`。"
            ),
            "",
            _table(
                ["task", "工作", "耗時(示意)", "優先權(示意)", "初始狀態"], enqueued
            ),
            "",
            "**甘特圖**（`#` = 執行中，`.` = 沒在跑）：",
            "",
            _table(["task", "工作", "時間", "時間軸", "終態"], gantt_rows),
            "",
            f"事件流共 {events_before} 筆，依 `event_id` 遞增：",
            "",
            _table(["event_id", "type", "sim_time", "state_version"], event_rows),
            "",
            (
                "**冪等**：再用同一個 `idempotency_key` 送一次 `ENQUEUE_TASK`，"
                f"CORE 回 `cached={replay['cached']}`、新增事件 {events_after - events_before} 筆。"
                "重送不會把工作做兩次（`docs/22` §3.6）。"
            ),
            "",
            "同一指令序列重跑會得到同樣的事件順序，見第 5 節。",
        ]
    )


async def section_save_load(demo: Demo) -> str:
    before = len(demo.engine.state.tasks)
    saved = demo.store.create_save(demo.engine.state, label="mvp-demo")

    await demo.command(
        "ENQUEUE_TASK",
        {"name": "存檔後追加的工作", "burst_seconds": 2},
        "after-save",
    )
    mutated = len(demo.engine.state.tasks)

    restored = demo.store.load_save(saved["save_id"])
    demo.engine.restore(WorldState.from_dict(restored["state"]))
    after = len(demo.engine.state.tasks)

    return "\n".join(
        [
            "## 4. 存檔與讀檔",
            "",
            "依據 `docs/08-04`、`docs/22` §3.7–3.8、`docs/20` §3。",
            "",
            _table(
                ["步驟", "工作數"],
                [
                    ["存檔前", str(before)],
                    ["存檔 `save_id`", str(saved["save_id"])],
                    ["存檔後用真的 command 追加一件工作", str(mutated)],
                    ["讀回存檔", str(after)],
                ],
            ),
            "",
            f"checksum：`{saved['checksum'][:16]}…`（SHA-256，讀檔前驗證）。",
            (
                "讀檔**不重播**已結算事件：存檔本身即最終結果，因此工作數回到存檔當下，"
                "不會重複扣料或重算收入。"
            ),
        ]
    )


async def _replay(db_path: Path) -> list[tuple[str, int]]:
    demo = Demo(db_path)
    await demo.play_scenario()
    return [(event["type"], int(event["sim_time"])) for event in demo.events]


async def section_determinism(
    demo: Demo, db_path: Path, live: list[tuple[str, int]]
) -> str:
    run_a = await _replay(db_path.with_name("demo_mvp_run_a.sqlite"))
    run_b = await _replay(db_path.with_name("demo_mvp_run_b.sqlite"))
    identical = run_a == run_b == live
    same = "是" if identical else "否"
    return "\n".join(
        [
            "## 5. 決定性（同一輸入 → 同一事件序列）",
            "",
            (
                "依據 `docs/17` §5.4。兩個全新的暫存 DB 各跑一次同樣的指令序列，"
                "再和本頁 demo 的結果逐筆比對 `(type, sim_time)`。"
            ),
            "",
            _table(
                ["比較", "事件數", "序列一致"],
                [
                    ["run A ↔ run B", str(len(run_a)), same],
                    ["run A ↔ 本頁 demo", str(len(live)), same],
                ],
            ),
            "",
            (
                "比對的是事件類型與模擬時間；`event_id` 會隨 DB 重建而從 1 開始，"
                "不列入比較。"
            ),
        ]
    )


async def section_perf(demo: Demo) -> str:
    samples: list[float] = []
    for index in range(PERF_SAMPLES):
        started = time.perf_counter()
        await demo.command(
            "ENQUEUE_TASK",
            {"burst_seconds": 2 + index % 3},
            f"perf-{index}",
        )
        samples.append((time.perf_counter() - started) * 1000)

    warm = samples[5:]
    scheduler_samples: list[float] = []
    specs = [
        TaskSpec(id=f"P-{index:03d}", arrival=index % 10, burst=1 + index % 7)
        for index in range(30)
    ]
    for _ in range(50):
        started = time.perf_counter()
        run_scheduler("priority_aging", specs)
        scheduler_samples.append((time.perf_counter() - started) * 1000)

    return "\n".join(
        [
            "## 6. 效能（tick 預算）",
            "",
            "依據 `docs/17` §11.4（每 tick < 5 ms，超過要記錄）、`docs/24`。",
            "",
            _table(
                ["項目", "p50", "p90", "max"],
                [
                    [
                        f"指令（in-process，{len(warm)} 次暖機樣本）",
                        f"{statistics.median(warm):.2f} ms",
                        f"{sorted(warm)[int(len(warm) * 0.9)]:.2f} ms",
                        f"{max(warm):.2f} ms",
                    ],
                    [
                        "30 工作的 Priority+Aging（50 次取中位數）",
                        f"{statistics.median(scheduler_samples):.2f} ms",
                        "—",
                        f"{max(scheduler_samples):.2f} ms",
                    ],
                ],
            ),
            "",
            (
                "這裡量的是 in-process 成本；含 HTTP 的值見 `docs/24`"
                "（p50 2.23 ms、max 3.65 ms）。"
            ),
        ]
    )


def section_limits() -> str:
    return "\n".join(
        [
            "## 7. 這個 MVP 的邊界",
            "",
            _table(
                ["已具備", "尚未具備"],
                [
                    [
                        "CORE 指令、事件、決定性",
                        "訂單／顧客／庫存／日循環（`11` 未定案）",
                    ],
                    ["5 個排程策略與指標", "其餘 7 類演算法（`21` §7）"],
                    ["存檔／讀檔、checksum", "FE 9 頁（`13`、`22-01`）"],
                    ["REST + WebSocket 契約", "AI 服務本體（`19`）"],
                    ["tick 預算 2.23 ms", "多 worker、壓測（`23` §4.3）"],
                ],
            ),
            "",
            "## 8. 報告骨架（這個 demo 對應的章節）",
            "",
            _table(
                ["報告章節", "內容來源", "現況"],
                [
                    ["動機與範圍", "`01`、`02`", "有文件"],
                    ["系統架構", "`17`", "有文件＋可執行"],
                    ["OS 演算法", "`03`、`21`", "5/12 已實作"],
                    ["資料模型", "`20`", "schema v2"],
                    ["介面契約", "`22`", "11 端點"],
                    ["測試與品質", "`24`", "37 + 9 測試"],
                    ["限制與未來", "`21` §7、`22` §8、`23` §11", "有清單"],
                ],
            ),
            "",
            (
                "要出完整報告時，把這七節補上截圖、需求對照與未定項目即可；"
                "demo 本身不需要重寫。"
            ),
        ]
    )


async def build_report(db_path: Path) -> str:
    demo = Demo(db_path)
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    header = "\n".join(
        [
            "# 鼠於我的小餐館｜MVP 示範",
            "",
            (
                f"由 `demo/mvp.py` 自動產生於 {now}；CORE version `{core.__version__}`。"
                f"示範資料庫：`{db_path.as_posix()}`（暫存，可刪）。"
            ),
            "",
            (
                "> 本文的工作秒數、優先權與 4 件工作負載都是**示範假設**，不是遊戲規格"
                "（`docs/06-02` §二、`docs/03` §6）。世界狀態、事件與量測數字"
                "則是實際執行結果。"
            ),
            "",
            "## 0. 這個 MVP 想證明什麼",
            "",
            "- CORE 是唯一 authoritative world，可在沒有 FE／AI 的情況下獨立執行。",
            "- OS 排程策略可互相比較，且只有非搶佔式能驅動世界指派。",
            "- 世界裁決會留下事件與快照；存檔可驗證，讀檔不重播過去事件。",
            "- 同樣輸入產生同樣事件序列，不是靠運氣。",
            "- tick 預算（< 5 ms）是量出來的，不是宣稱的。",
        ]
    )

    world = section_world(demo)
    algorithms = section_algorithms()
    world_run = await section_world_run(demo)
    live = [(event["type"], int(event["sim_time"])) for event in demo.events]
    parts = [
        header,
        world,
        algorithms,
        world_run,
        await section_save_load(demo),
        await section_determinism(demo, db_path, live),
        await section_perf(demo),
        section_limits(),
    ]
    return "\n\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CORE MVP demo.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the markdown report to this path as well as stdout",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(".tmp") / "demo_mvp.sqlite",
        help="scratch database for the demo (default .tmp/demo_mvp.sqlite)",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(build_report(args.db))
    # The report is UTF-8; a cp950 console would otherwise raise on characters
    # it cannot encode (the file written below is always UTF-8).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"[demo] report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
