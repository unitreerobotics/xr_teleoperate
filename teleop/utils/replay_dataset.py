#!/usr/bin/env python3
"""
Interactive dataset viewer for Rerun.

- Spawns a single Rerun viewer.
- Lazily logs the currently selected episode.
- Use terminal input to switch episodes:
    n = next, p = previous, <number> = jump, q = quit

Usage:
  python view_dataset.py --task-dir /path/to/task_dir
  python view_dataset.py --task-dir /path/to/task_dir --start 12 --window 60 --memory-limit 500MB
  python view_dataset.py --task-dir /path/to/task_dir --playback online --hz 30

Expected layout:
  task_dir/
    episode_0012/
      data.json
      colors/...
      depths/...
      audios/...
"""

import os
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime

os.environ.setdefault("RUST_LOG", "error")

import rerun as rr
import rerun.blueprint as rrb


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _try_log_image(path: Path, entity_path: str) -> None:
    """Prefer logging encoded images from disk; fallback to OpenCV decode."""
    if not path.exists():
        return

    try:
        rr.log(entity_path, rr.ImageEncoded(path=str(path)))
        return
    except Exception:
        pass

    try:
        import cv2

        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            return
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rr.log(entity_path, rr.Image(img))
    except Exception:
        return


class EpisodeReader:
    def __init__(self, task_dir: str, json_file: str = "data.json"):
        self.task_dir = Path(task_dir).expanduser()
        self.json_file = json_file

    def episode_dir(self, episode_idx: int) -> Path:
        return self.task_dir / f"episode_{episode_idx:04d}"

    def load_index(self, episode_idx: int) -> list[dict]:
        """Loads metadata/paths from data.json (no image decoding)."""
        ep_dir = self.episode_dir(episode_idx)
        json_path = ep_dir / self.json_file
        if not json_path.exists():
            raise FileNotFoundError(f"Missing: {json_path}")

        j = _load_json(json_path)
        frames = j.get("data", [])
        out: list[dict] = []

        for fr in frames:
            colors = (fr.get("colors") or {}).copy()
            depths = (fr.get("depths") or {}).copy()

            colors = {k: (ep_dir / v) for k, v in colors.items() if v}
            depths = {k: (ep_dir / v) for k, v in depths.items() if v}

            out.append(
                {
                    "idx": fr.get("idx", 0),
                    "colors": colors,
                    "depths": depths,
                    "states": fr.get("states") or {},
                    "actions": fr.get("actions") or {},
                    "tactiles": fr.get("tactiles") or {},
                    "audios": fr.get("audios") or {},
                }
            )

        return out


class RerunDatasetViewer:
    def __init__(self, window: int = 60, memory_limit: str | None = None):
        self.window = window

        rr.init(datetime.now().strftime("DatasetViewer_%Y%m%d_%H%M%S"))
        if memory_limit:
            rr.spawn(memory_limit=memory_limit, hide_welcome_screen=True)
        else:
            rr.spawn(hide_welcome_screen=True)

        # Cache: episode_idx -> frames already loaded/logged?
        self._frames_cache: dict[int, list[dict]] = {}
        self._logged_episodes: set[int] = set()

    @staticmethod
    def _ep_prefix(ep: int) -> str:
        # One folder per episode inside the recording
        return f"episode_{ep:04d}/"

    def send_blueprint(self, ep: int, color_keys: list[str]) -> None:
        """Update UI to focus on a specific episode prefix."""
        prefix = self._ep_prefix(ep)
        views: list[rrb.BlueprintLike] = []

        # Time series views
        ts_origins = [
            f"{prefix}left_arm/states/qpos",
            f"{prefix}left_arm/actions/qpos",
            f"{prefix}right_arm/states/qpos",
            f"{prefix}right_arm/actions/qpos",
            f"{prefix}left_ee/states/qpos",
            f"{prefix}left_ee/actions/qpos",
            f"{prefix}right_ee/states/qpos",
            f"{prefix}right_ee/actions/qpos",
        ]

        for origin in ts_origins:
            views.append(
                rrb.TimeSeriesView(
                    origin=origin,
                    time_ranges=[
                        rrb.VisibleTimeRange(
                            "idx",
                            start=rrb.TimeRangeBoundary.cursor_relative(seq=-self.window),
                            end=rrb.TimeRangeBoundary.cursor_relative(),
                        )
                    ],
                    plot_legend=rrb.PlotLegend(visible=True),
                )
            )

        # Images [(2,97,-1),(3,98,-1),(15,74,-1),(26,96,-1),(32,74,-1),(50,98,-1),(52,87,-1),(67,72,-1),(97,168,-1)]  
        for ck in color_keys:
            views.append(
                rrb.Spatial2DView(
                    origin=f"{prefix}colors/{ck}",
                    time_ranges=[
                        rrb.VisibleTimeRange(
                            "idx",
                            start=rrb.TimeRangeBoundary.cursor_relative(seq=-self.window),
                            end=rrb.TimeRangeBoundary.cursor_relative(),
                        )
                    ],
                )
            )

        rr.send_blueprint(
            rrb.Grid(
                contents=views,
                grid_columns=2,
                column_shares=[1, 1],
            )
        )

    def _log_frame(self, ep: int, fr: dict) -> None:
        prefix = self._ep_prefix(ep)
        rr.set_time_sequence("idx", int(fr.get("idx", 0)))

        # states/actions qpos as scalars
        for section_name in ("states", "actions"):
            section = fr.get(section_name, {}) or {}
            for part, info in section.items():
                if part == "body" or not info:
                    continue
                values = info.get("qpos", []) or []
                for j, val in enumerate(values):
                    rr.log(f"{prefix}{part}/{section_name}/qpos/{j}", rr.Scalar(float(val)))

        # colors
        colors: dict[str, Path] = fr.get("colors", {}) or {}
        for ck, path in colors.items():
            _try_log_image(path, f"{prefix}colors/{ck}")

    def ensure_episode_loaded_and_logged(
        self,
        reader: EpisodeReader,
        ep: int,
        playback: str = "offline",
        hz: float = 30.0,
    ) -> list[str]:
        """Load frames for episode ep (cached) and log them once. Returns color_keys."""
        if ep not in self._frames_cache:
            self._frames_cache[ep] = reader.load_index(ep)

        frames = self._frames_cache[ep]
        color_keys = sorted({k for fr in frames for k in (fr.get("colors") or {}).keys()})

        if ep not in self._logged_episodes:
            if playback == "online":
                dt = 1.0 / float(hz)
                for fr in frames:
                    self._log_frame(ep, fr)
                    time.sleep(dt)
            else:
                for fr in frames:
                    self._log_frame(ep, fr)
            self._logged_episodes.add(ep)

        return color_keys


def list_episodes(task_dir: Path) -> list[int]:
    """Return available episode indices by scanning episode_XXXX folders."""
    eps: list[int] = []
    pat = re.compile(r"episode_(\d{4})$")
    for p in task_dir.iterdir():
        if not p.is_dir():
            continue
        m = pat.match(p.name)
        if m:
            eps.append(int(m.group(1)))
    return sorted(eps)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=str, required=True)
    parser.add_argument("--start", type=int, default=None, help="Start episode index (e.g. 12)")
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--memory-limit", type=str, default=None, help="e.g. 200MB or 1GB")
    parser.add_argument("--playback", choices=["offline", "online"], default="offline")
    parser.add_argument("--hz", type=float, default=30.0)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).expanduser()
    eps = list_episodes(task_dir)
    if not eps:
        raise RuntimeError(f"No episode_XXXX folders found under: {task_dir}")

    # Choose initial episode
    if args.start is not None:
        if args.start not in eps:
            raise RuntimeError(f"--start {args.start} not found. Available range: {eps[0]}..{eps[-1]}")
        cur_idx = eps.index(args.start)
    else:
        cur_idx = 0

    reader = EpisodeReader(task_dir=str(task_dir))
    viewer = RerunDatasetViewer(window=args.window, memory_limit=args.memory_limit)

    def show_episode(ep: int) -> None:
        color_keys = viewer.ensure_episode_loaded_and_logged(
            reader,
            ep,
            playback=args.playback,
            hz=args.hz,
        )
        viewer.send_blueprint(ep, color_keys=color_keys)
        print(f"\nNow showing episode {ep}  (folder episode_{ep:04d})")
        print(f"Logged episodes so far: {len(viewer._logged_episodes)} / {len(eps)}")

    # Show first
    show_episode(eps[cur_idx])

    # Interactive loop
    print("\nCommands: n=next, p=prev, <number>=jump to episode, q=quit\n")
    while True:
        cmd = input("viewer> ").strip().lower()
        if cmd in ("q", "quit", "exit"):
            break
        elif cmd in ("n", "next"):
            cur_idx = min(cur_idx + 1, len(eps) - 1)
            show_episode(eps[cur_idx])
        elif cmd in ("p", "prev", "previous"):
            cur_idx = max(cur_idx - 1, 0)
            show_episode(eps[cur_idx])
        elif cmd.isdigit():
            ep = int(cmd)
            if ep not in eps:
                print(f"Episode {ep} not found. Available range: {eps[0]}..{eps[-1]}")
                continue
            cur_idx = eps.index(ep)
            show_episode(eps[cur_idx])
        else:
            print("Unknown command. Use: n, p, <number>, q")


if __name__ == "__main__":
    main()
