#!/usr/bin/env python3
"""
Merge multiple dataset directories containing episode folders into one dataset.

Example:
  utils/merge_datasets /path/dataset1 /path/dataset2

Input episode names can be either:
  - episode0001
  - episode_0001
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


EPISODE_RE = re.compile(r"^episode_?(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge two or more dataset directories into one directory with "
            "sequential episode numbering."
        )
    )
    parser.add_argument(
        "datasets",
        nargs="+",
        help="Input dataset directories containing episode folders.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output dataset directory. Default: <parent_of_first_input>/"
            "<dataset1>_<dataset2>_..."
        ),
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=4,
        help="Zero-padding width for output episode names (default: 4).",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Starting index for output episode numbering (default: 0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without copying files.",
    )
    return parser.parse_args()


def default_output_dir(inputs: Sequence[Path]) -> Path:
    names = [p.name.rstrip("/") for p in inputs]
    return inputs[0].parent / "_".join(names)


def collect_episode_dirs(dataset_dir: Path) -> List[Tuple[int, Path]]:
    episodes: List[Tuple[int, Path]] = []
    for entry in dataset_dir.iterdir():
        if not entry.is_dir():
            continue
        match = EPISODE_RE.match(entry.name)
        if not match:
            continue
        episodes.append((int(match.group(1)), entry))
    episodes.sort(key=lambda x: (x[0], x[1].name))
    return episodes


def ensure_inputs(inputs: Iterable[Path]) -> List[Path]:
    paths = [p.resolve() for p in inputs]
    if len(paths) < 2:
        raise ValueError("Provide at least two dataset paths.")
    for path in paths:
        if not path.exists():
            raise ValueError(f"Input path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Input path is not a directory: {path}")
    return paths


def main() -> int:
    args = parse_args()

    try:
        input_dirs = ensure_inputs(Path(p) for p in args.datasets)
    except ValueError as exc:
        eprint(f"Error: {exc}")
        return 2

    output_dir = Path(args.output).resolve() if args.output else default_output_dir(input_dirs)
    if output_dir.exists() and any(output_dir.iterdir()):
        eprint(f"Error: output directory exists and is not empty: {output_dir}")
        eprint("Use --output to choose another directory or empty the existing one.")
        return 2

    if args.padding < 1:
        eprint("Error: --padding must be >= 1")
        return 2
    if args.start_index < 0:
        eprint("Error: --start-index must be >= 0")
        return 2

    merged_sources: List[Path] = []
    for dataset_dir in input_dirs:
        episodes = collect_episode_dirs(dataset_dir)
        if not episodes:
            eprint(f"Warning: no episode folders found in {dataset_dir}")
            continue
        merged_sources.extend(ep_path for _idx, ep_path in episodes)

    if not merged_sources:
        eprint("Error: no episode folders found in any input dataset.")
        return 2

    print(f"Output directory: {output_dir}")
    print(f"Total episodes to merge: {len(merged_sources)}")

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    next_idx = args.start_index
    for src_ep in merged_sources:
        dst_name = f"episode_{next_idx:0{args.padding}d}"
        dst_ep = output_dir / dst_name
        print(f"{src_ep} -> {dst_ep}")
        if not args.dry_run:
            shutil.copytree(src_ep, dst_ep)
        next_idx += 1

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
