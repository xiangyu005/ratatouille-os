"""Low-cost architecture tests for the invariants in docs/17.

These are deliberately simple: parse imports instead of running a framework.
"""

from __future__ import annotations

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
FORBIDDEN_EVERYWHERE = ("ai", "frontend")
PURE_LAYERS = ("domain", "algorithms")
FORBIDDEN_IN_PURE_LAYERS = ("fastapi", "sqlite3", "numpy", "numba")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_core_never_imports_ai_or_frontend() -> None:
    violations: list[str] = []
    for path in CORE.rglob("*.py"):
        if "tests" in path.parts:
            continue
        for module in imported_modules(path):
            root = module.split(".", 1)[0]
            if root in FORBIDDEN_EVERYWHERE:
                violations.append(f"{path.relative_to(CORE)} imports {module}")
    assert not violations, "\n".join(violations)


def test_domain_and_algorithms_stay_framework_free() -> None:
    violations: list[str] = []
    for layer in PURE_LAYERS:
        for path in (CORE / layer).rglob("*.py"):
            for module in imported_modules(path):
                root = module.split(".", 1)[0]
                if root in FORBIDDEN_IN_PURE_LAYERS:
                    violations.append(f"{path.relative_to(CORE)} imports {module}")
    assert not violations, "\n".join(violations)


def test_sqlite_is_confined_to_persistence() -> None:
    violations: list[str] = []
    for path in CORE.rglob("*.py"):
        if "tests" in path.parts or "persistence" in path.parts:
            continue
        if "sqlite3" in imported_modules(path):
            violations.append(str(path.relative_to(CORE)))
    assert not violations, "\n".join(violations)
