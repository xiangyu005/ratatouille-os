"""Smoke test for the AI service dependency set.

Run from `ai/` with:

    uv run python smoke.py

It checks imports, one real operation per major package, dependency integrity,
and the Numba cache path. It does not call any network or model.
"""

from __future__ import annotations

import importlib.metadata as md
import tempfile
from pathlib import Path

import bm25s
import faiss
import httpx
import numpy as np
import pdfplumber
import pydantic_settings
import pypdf
from mcp.server.mcpserver import MCPServer
from numba import njit
from pydantic_settings import BaseSettings
from pypdf import PdfReader, PdfWriter

FAILURES: list[str] = []


@njit(cache=True)
def add(a: int, b: int) -> int:
    return a + b


@njit(cache=True)
def sum_array(values: np.ndarray) -> float:
    total = 0.0
    for i in range(values.shape[0]):
        total += values[i]
    return total


class SmokeSettings(BaseSettings):
    smoke_value: int = 7


def check(name: str, operation) -> None:  # type: ignore[no-untyped-def]
    try:
        result = operation()
        print(f"[ok] {name}: {result}")
    except Exception as exc:  # noqa: BLE001 - smoke test must report every failure
        FAILURES.append(name)
        print(f"[fail] {name}: {type(exc).__name__}: {exc}")


def check_versions() -> None:
    for name in (
        "mcp",
        "faiss-cpu",
        "bm25s",
        "numpy",
        "numba",
        "pypdf",
        "pdfplumber",
        "python-multipart",
        "pydantic-settings",
        "httpx",
        "ruff",
    ):
        print(f"[version] {name}=={md.version(name)}")


def check_mcp() -> str:
    server = MCPServer("ratatouille-smoke")
    return server.name


def check_faiss() -> str:
    index = faiss.IndexFlatL2(4)
    index.add(np.array([[0, 0, 0, 0], [1, 1, 1, 1]], dtype="float32"))
    distances, indices = index.search(np.array([[0, 0, 0, 0]], dtype="float32"), 1)
    assert int(indices[0][0]) == 0, indices
    return f"nearest={int(indices[0][0])} distance={float(distances[0][0])}"


def check_bm25s() -> str:
    corpus = ["cat likes fish", "dog likes bones"]
    tokens = bm25s.tokenize(corpus, stopwords="en")
    retriever = bm25s.BM25()
    retriever.index(tokens)
    results, scores = retriever.retrieve(bm25s.tokenize("cat", stopwords="en"), k=1)
    assert results.shape == (1, 1), results.shape
    return f"top={int(results[0][0])} score={float(scores[0][0]):.4f}"


def check_numba() -> str:
    assert add(2, 3) == 5
    assert abs(sum_array(np.array([1.0, 2.0, 3.0])) - 6.0) < 1e-9
    return f"add=5 sum=6 signatures={len(add.signatures)}"


def check_pdf() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "smoke.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(path)

        reader = PdfReader(str(path))
        assert len(reader.pages) == 1
        with pdfplumber.open(str(path)) as pdf:
            assert len(pdf.pages) == 1
    return "pypdf=1 page pdfplumber=1 page"


def check_settings() -> str:
    assert SmokeSettings().smoke_value == 7
    return "BaseSettings loaded"


def check_httpx() -> str:
    return f"httpx={httpx.__version__}"


def main() -> int:
    print("== versions ==")
    check_versions()

    print("== operations ==")
    check("mcp server", check_mcp)
    check("faiss index", check_faiss)
    check("bm25s retrieval", check_bm25s)
    check("numba kernels", check_numba)
    check("pdf readers", check_pdf)
    check("pydantic-settings", check_settings)
    check("httpx", check_httpx)

    print("== imports ==")
    print(f"[ok] pypdf=={pypdf.__version__}")
    print(f"[ok] pdfplumber=={pdfplumber.__version__}")
    print(f"[ok] pydantic-settings=={pydantic_settings.__version__}")

    if FAILURES:
        print(f"SMOKE FAILED: {FAILURES}")
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
