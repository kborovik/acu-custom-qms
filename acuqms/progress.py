"""Per-step CLI progress on stderr (T16 / I.cmd).

Lines are tab-separated: step, target, result, elapsed.
Stdout stays path / status / seeded.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TextIO


@dataclass
class Progress:
    step: str
    target: str
    result: str = "ok"


def emit(
    step: str,
    target: str,
    result: str,
    elapsed: float,
    *,
    file: TextIO | None = None,
) -> None:
    out = sys.stderr if file is None else file
    print(f"{step}\t{target}\t{result}\t{elapsed:.2f}s", file=out, flush=True)


def heartbeat(step: str, detail: str, *, file: TextIO | None = None) -> None:
    """Poll status on stderr. Two columns — not the completion 4-col schema (V19 / B12)."""
    out = sys.stderr if file is None else file
    print(f"{step}\t{detail}", file=out, flush=True)


@contextmanager
def progress(step: str, target: str) -> Iterator[Progress]:
    rec = Progress(step=step, target=target)
    t0 = time.monotonic()
    try:
        yield rec
    except Exception:
        rec.result = "fail"
        raise
    finally:
        emit(rec.step, rec.target, rec.result, time.monotonic() - t0)
