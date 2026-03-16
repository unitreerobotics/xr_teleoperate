#!/usr/bin/env python3
"""
Show first frame from each episode in a grid, titled with episode folder names.

Example:
  python teleop/utils/show_first_frames.py --task-dir teleop/utils/data
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt


EP_RE = re.compile(r"^episode_(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pick_first_color_path(data: Dict[str, Any], camera_key: Optional[str]) -> Optional[str]:
    frames = data.get("data")
    if not isinstance(frames, list) or not frames:
        return None
    first = frames[0]
    if not isinstance(first, dict):
        return None
    colors = first.get("colors")
    if not isinstance(colors, dict) or not colors:
        return None

    if camera_key:
        path = colors.get(camera_key)
        return path if isinstance(path, str) else None

    # Stable default when not provided.
    if "color_0" in colors and isinstance(colors["color_0"], str):
        return colors["color_0"]
    for _, rel in sorted(colors.items()):
        if isinstance(rel, str):
            return rel
    return None


def collect_first_frames(task_dir: Path, camera_key: Optional[str]) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    episodes: List[Tuple[int, Path]] = []

    for p in task_dir.iterdir():
        if not p.is_dir():
            continue
        m = EP_RE.match(p.name)
        if not m:
            continue
        episodes.append((int(m.group(1)), p))
    episodes.sort(key=lambda x: x[0])

    for _, ep_dir in episodes:
        data_path = ep_dir / "data.json"
        if not data_path.exists():
            eprint(f"WARNING: skipping {ep_dir.name}, missing data.json")
            continue

        try:
            data = load_json(data_path)
        except (OSError, json.JSONDecodeError) as ex:
            eprint(f"WARNING: skipping {ep_dir.name}, invalid data.json ({ex})")
            continue

        rel = pick_first_color_path(data, camera_key)
        if not rel:
            eprint(f"WARNING: skipping {ep_dir.name}, missing first-frame color path")
            continue

        img_path = ep_dir / rel
        if not img_path.exists():
            eprint(f"WARNING: skipping {ep_dir.name}, missing image: {img_path}")
            continue

        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            eprint(f"WARNING: skipping {ep_dir.name}, failed to decode: {img_path}")
            continue

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        out.append((ep_dir.name, img_rgb))

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", required=True, help="Directory containing episode_XXXX folders")
    ap.add_argument(
        "--camera-key",
        default=None,
        help="Color key to use from first frame (e.g. color_0). Default: color_0 if present, else first sorted key.",
    )
    ap.add_argument("--page-size", type=int, default=16, help="How many episodes per window (default: 16)")
    ap.add_argument("--cols", type=int, default=4, help="Grid columns per window (default: 4)")
    ap.add_argument("--figscale", type=float, default=4.5, help="Figure scale per cell (default: 4.5)")
    args = ap.parse_args()

    task_dir = Path(args.task_dir).expanduser().resolve()
    if not task_dir.exists() or not task_dir.is_dir():
        eprint(f"ERROR: --task-dir is not a directory: {task_dir}")
        sys.exit(2)
    if args.cols <= 0:
        eprint("ERROR: --cols must be > 0")
        sys.exit(2)
    if args.page_size <= 0:
        eprint("ERROR: --page-size must be > 0")
        sys.exit(2)
    if args.figscale <= 0:
        eprint("ERROR: --figscale must be > 0")
        sys.exit(2)

    frames = collect_first_frames(task_dir, args.camera_key)
    if not frames:
        eprint("ERROR: no first frames found to display")
        sys.exit(2)

    n = len(frames)
    page_size = args.page_size
    num_pages = math.ceil(n / page_size)

    for page_idx in range(num_pages):
        start = page_idx * page_size
        end = min(start + page_size, n)
        batch = frames[start:end]
        batch_n = len(batch)

        cols = min(args.cols, batch_n)
        rows = math.ceil(batch_n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(cols * args.figscale, rows * args.figscale))
        if rows == 1 and cols == 1:
            axes_list = [axes]
        elif rows == 1:
            axes_list = list(axes)
        elif cols == 1:
            axes_list = [axes[r] for r in range(rows)]
        else:
            axes_list = [axes[r, c] for r in range(rows) for c in range(cols)]

        for i, ax in enumerate(axes_list):
            if i >= batch_n:
                ax.axis("off")
                continue
            ep_name, img = batch[i]
            ax.imshow(img)
            ax.set_title(ep_name, fontsize=12)
            ax.axis("off")

        fig.suptitle(f"First Frames {start + 1}-{end} of {n} (page {page_idx + 1}/{num_pages})", fontsize=14)
        plt.tight_layout(rect=[0, 0.02, 1, 0.96])
        # Block until the current window is closed, then continue with next page.
        plt.show(block=True)


if __name__ == "__main__":
    main()
