"""Parent process: parse every PDF of the spike set in a subprocess with a timeout.

Run from the repo root (pypdf comes from the project venv):
    uv run python spikes/1.6-pdf/parse_set.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from text_quality import assess

HERE = Path(__file__).resolve().parent
WORKER = HERE / "pdf_worker.py"
TIMEOUT_S = 5.0

PDF_SET = [
    HERE.parents[1] / "data" / "samples" / "sample_cv.pdf",
    HERE / "real" / "real_cv.pdf",
    HERE / "real" / "canva_cv.pdf",
    HERE / "hard" / "two_column.pdf",
    HERE / "hard" / "garbled.pdf",
    HERE / "hard" / "scanned.pdf",
]


class ParseTimeout(Exception):
    """The worker did not finish in time and was killed."""


async def parse_pdf(
    content: bytes, timeout_s: float = TIMEOUT_S, hang: bool = False, engine: str = "pypdf"
) -> dict:
    """Extract text from PDF bytes in a child process; kill it if it exceeds the timeout.

    `python -I` (isolated mode) ignores PYTHON* env vars and the current directory,
    so nothing next to the worker can be imported by accident.
    """
    args = [sys.executable, "-I", str(WORKER), "--engine", engine] + (["--hang"] if hang else [])
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(content), timeout_s)
    except TimeoutError:
        proc.kill()  # SIGKILL: the OS stops it even inside a busy loop
        await proc.wait()  # reap it, so no zombie process is left behind
        raise ParseTimeout(f"pid {proc.pid} killed after {timeout_s}s") from None
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace")[-300:])
    return json.loads(stdout)


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # signal 0 = "does this process exist?"
    except ProcessLookupError:
        return False
    return True


async def main() -> None:
    engine = sys.argv[1] if len(sys.argv) > 1 else "pypdf"
    print(f"engine: {engine}")
    header = f"{'file':<16} {'pages':>5} {'chars/page':>10} {'bad chars':>9} {'words':>6} {'seconds':>7}  verdict"
    print(header)
    for path in PDF_SET:
        start = time.perf_counter()
        result = await parse_pdf(path.read_bytes(), engine=engine)
        elapsed = time.perf_counter() - start
        q = assess(result["pages"])
        print(
            f"{path.name:<16} {result['page_count']:>5} {q.chars_per_page:>10.0f} "
            f"{q.bad_char_ratio:>9.1%} {q.word_ratio:>6.1%} {elapsed:>7.2f}  {q.verdict}"
        )

    print("\nTimeout check (worker stuck in a busy loop, timeout 1 s):")
    start = time.perf_counter()
    try:
        await parse_pdf(b"", timeout_s=1.0, hang=True, engine=engine)
    except ParseTimeout as exc:
        pid = int(str(exc).split()[1])
        print(f"  {exc} in {time.perf_counter() - start:.2f}s; still alive: {is_alive(pid)}")


if __name__ == "__main__":
    asyncio.run(main())
