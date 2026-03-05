#!/usr/bin/env python3
"""
Cut multiple Unitree-style episodes from a list of tuples.

Usage:
  python cut_multiple_episodes.py --task-dir /path/to/task_dir \
    --cuts "[(12, 0, -1), (13, 10, 50)]"

Each tuple is (episode_number, start_idx, end_idx). Use -1 for end_idx to cut
through the last frame of the episode.
"""

import argparse
import ast
import shutil
import tempfile
from pathlib import Path

try:
    from teleop.utils.cut_episode import copy_rel_file, load_json, save_json
except ModuleNotFoundError:
    # Supports direct script execution from within teleop/ (no top-level teleop package on sys.path).
    from cut_episode import copy_rel_file, load_json, save_json


def parse_cuts(raw: str) -> list[tuple[int, int, int]]:
    """Parse a CLI string like '[(12, 0, -1), (13, 10, 50)]' into tuples."""
    try:
        parsed = ast.literal_eval(raw)
    except Exception as e:  # pragma: no cover - CLI parsing only
        raise ValueError(f"Could not parse cuts: {e}") from e

    if not isinstance(parsed, (list, tuple)):
        raise ValueError("Cuts must be a list/tuple of (episode, start, end).")

    cuts: list[tuple[int, int, int]] = []
    for item in parsed:
        if not (isinstance(item, (list, tuple)) and len(item) == 3):
            raise ValueError(f"Invalid cut tuple: {item}")
        ep, start, end = item
        cuts.append((int(ep), int(start), int(end)))
    return cuts


def cut_single(task_dir: Path, episode_idx: int, start_idx: int, end_idx: int, keep_idx: bool) -> None:
    src_ep = task_dir / f"episode_{episode_idx:04d}"
    dst_ep = src_ep  # overwrite in place for this helper

    if dst_ep.exists():
        resp = input(f"You have selected to overwrite episode {episode_idx:04d}, confirm? (y/n) ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return

    # Build in a temporary folder first to avoid clobbering the source on failure.
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"{src_ep.name}_cut_", dir=task_dir))
    dst_build = tmp_dir

    src_json = src_ep / "data.json"
    if not src_json.exists():
        raise FileNotFoundError(f"Missing {src_json}")

    j = load_json(src_json)
    frames = j.get("data", [])
    if not frames:
        raise ValueError(f"No frames under 'data' in {src_json}.")

    start = max(0, start_idx)
    end_arg = len(frames) if end_idx is None or end_idx == -1 else end_idx
    end = min(len(frames), end_arg)
    if end <= start:
        raise ValueError(f"Invalid range for episode {episode_idx}: start={start}, end={end}, len={len(frames)}")

    cut = frames[start:end]

    # Create output episode folder and ALWAYS keep these subfolders
    dst_build.mkdir(parents=True, exist_ok=True)
    (dst_build / "colors").mkdir(parents=True, exist_ok=True)
    (dst_build / "depths").mkdir(parents=True, exist_ok=True)
    (dst_build / "audios").mkdir(parents=True, exist_ok=True)

    # Copy referenced files (but don't delete anything / don't require they exist)
    for fr in cut:
        for section in ("colors", "depths", "audios"):
            sec = fr.get(section, {}) or {}
            for _, rel in sec.items():
                if not rel:
                    continue
                copy_rel_file(src_ep, dst_build, rel)

    # Optionally reindex idx
    if not keep_idx:
        for i, fr in enumerate(cut):
            fr["idx"] = i

    # Write new json
    out = dict(j)
    out["data"] = cut
    save_json(dst_build / "data.json", out)

    shutil.rmtree(src_ep)
    dst_build.rename(src_ep)

    print(f"Written cut episode: {src_ep}")
    print(f"Frames: {len(cut)}  (from [{start}:{end}))")
    print("Folders preserved: colors/, depths/, audios/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", required=True, type=str)
    ap.add_argument(
        "--cuts",
        required=True,
        type=str,
        help='List of tuples: "[(12, 0, -1), (13, 10, 50)]". Each tuple is (episode, start, end).',
    )
    ap.add_argument("--keep-idx", action="store_true",
                    help="Keep original 'idx' values. By default reindexes idx to 0..N-1.")
    args = ap.parse_args()

    task_dir = Path(args.task_dir)
    cuts = parse_cuts(args.cuts)

    for ep, start, end in cuts:
        cut_single(task_dir, ep, start, end, args.keep_idx)


if __name__ == "__main__":
    main()
