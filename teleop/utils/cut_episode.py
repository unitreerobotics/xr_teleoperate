#!/usr/bin/env python3
"""
Cut a Unitree-style episode into a new episode folder.
If --out-episode is omitted, the original episode is overwritten in-place.

Example:
  python cut_episode.py --task-dir /path/to/task_dir --episode 12 --start 100 --end 300 --out-episode 1012
Creates:
  /path/to/task_dir/episode_1012/...
"""

import argparse
import json
import shutil
import tempfile
from pathlib import Path


def load_json(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def copy_rel_file(src_ep_dir: Path, dst_ep_dir: Path, rel_path: str) -> None:
    """
    Copy a file referenced by rel_path into dst episode, preserving subfolders.
    If missing, we skip (but keep the folder structure if it exists in rel_path).
    """
    src = src_ep_dir / rel_path
    dst = dst_ep_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        # Keep going; folder still exists because we created dst.parent above.
        return

    shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", required=True, type=str)
    ap.add_argument("--episode", required=True, type=int, help="Input episode index (e.g. 12 -> episode_0012)")
    ap.add_argument("--start", required=True, type=int, help="Start frame index (0-based) in data.json['data']")
    ap.add_argument("--end", required=True, type=int, help="End frame index (exclusive)")
    ap.add_argument("--out-episode", type=int,
                    help="Output episode index (e.g. 1012 -> episode_1012). "
                         "If omitted, the original episode is replaced.")
    ap.add_argument("--keep-idx", action="store_true",
                    help="Keep original 'idx' values. By default reindexes idx to 0..N-1.")
    args = ap.parse_args()

    task_dir = Path(args.task_dir)
    src_ep = task_dir / f"episode_{args.episode:04d}"
    out_ep_idx = args.out_episode if args.out_episode is not None else args.episode
    dst_ep = task_dir / f"episode_{out_ep_idx:04d}"
    replace_in_place = src_ep == dst_ep
    will_overwrite = dst_ep.exists()

    if will_overwrite:
        resp = input(f"You have selected to overwrite episode {out_ep_idx:04d}, confirm? (y/n) ").strip().lower()
        if resp != "y":
            print("Aborted.")
            return

    # When replacing in place, build the new episode in a temporary folder first to avoid clobbering the source.
    if replace_in_place:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"{src_ep.name}_cut_", dir=task_dir))
        dst_build = tmp_dir
    else:
        dst_build = dst_ep
        if dst_build.exists():
            shutil.rmtree(dst_build)

    src_json = src_ep / "data.json"
    if not src_json.exists():
        raise FileNotFoundError(f"Missing {src_json}")

    j = load_json(src_json)
    frames = j.get("data", [])
    if not frames:
        raise ValueError("No frames under 'data' in data.json.")

    start = max(0, args.start)
    end = min(len(frames), args.end)
    if end <= start:
        raise ValueError(f"Invalid range: start={start}, end={end}, len={len(frames)}")

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
                # Paths in your json are usually like "colors/000000_color_0.jpg"
                copy_rel_file(src_ep, dst_build, rel)

    # Optionally reindex idx
    if not args.keep_idx:
        for i, fr in enumerate(cut):
            fr["idx"] = i

    # Write new json
    out = dict(j)
    out["data"] = cut
    save_json(dst_build / "data.json", out)

    if replace_in_place:
        shutil.rmtree(src_ep)
        dst_build.rename(src_ep)
        final_dst = src_ep
    else:
        final_dst = dst_build

    print(f"Written cut episode: {final_dst}")
    print(f"Frames: {len(cut)}  (from [{start}:{end}))")
    print("Folders preserved: colors/, depths/, audios/")


if __name__ == "__main__":
    main()
