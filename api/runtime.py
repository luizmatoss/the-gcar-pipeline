from pathlib import Path
from uuid import uuid4


def new_run_id() -> str:
    return uuid4().hex


def raw_output_paths(raw_dir: Path, run_id: str) -> tuple[Path, Path]:
    return (
        raw_dir / f"summary_{run_id}.jsonl",
        raw_dir / f"features_{run_id}.jsonl",
    )
