#!/usr/bin/env python3
"""
Rerun episode viewer.

Usage:
  python view_episode.py --task-dir /path/to/task_dir --episode 12 --mode offline
  python view_episode.py --task-dir /path/to/task_dir --episode 12 --mode online --hz 30 --window 60 --memory-limit 200MB

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
from pathlib import Path
from datetime import datetime

os.environ.setdefault("RUST_LOG", "error")

import rerun as rr
import rerun.blueprint as rrb


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _try_log_image(path: Path, entity_path: str) -> None:
    """
    Prefer logging encoded images from disk (fast + low RAM).
    Fallback to OpenCV decode if ImageEncoded isn't available in your rerun version.
    """
    if not path.exists():
        return

    try:
        # Most recent rerun-sdk versions support this:
        rr.log(entity_path, rr.ImageEncoded(path=str(path)))
        return
    except Exception:
        pass

    # Fallback decode path:
    try:
        import cv2

        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            return
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rr.log(entity_path, rr.Image(img))
    except Exception:
        # If OpenCV isn't available or decode fails, just skip.
        return


class EpisodeReader:
    def __init__(self, task_dir: str, json_file: str = "data.json"):
        self.task_dir = Path(task_dir)
        self.json_file = json_file

    def episode_dir(self, episode_idx: int) -> Path:
        return self.task_dir / f"episode_{episode_idx:04d}"

    def load_index(self, episode_idx: int) -> list[dict]:
        """
        Loads only metadata/paths from data.json (no image decoding).
        Returns list of per-frame dicts with idx, colors/depths paths, states/actions.
        """
        ep_dir = self.episode_dir(episode_idx)
        json_path = ep_dir / self.json_file
        if not json_path.exists():
            raise FileNotFoundError(f"Missing: {json_path}")

        j = _load_json(json_path)
        frames = j.get("data", [])
        out = []

        for fr in frames:
            colors = (fr.get("colors") or {}).copy()
            depths = (fr.get("depths") or {}).copy()

            # Convert relative paths to absolute Paths where possible
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
                    "torques": fr.get("torques") or {},
                    "audios": fr.get("audios") or {},
                }
            )

        return out


class RerunEpisodeLogger:
    def __init__(self, prefix: str = "", window: int = 60, memory_limit: str | None = None):
        self.prefix = prefix
        self.window = window

        rr.init(datetime.now().strftime("EpisodeViewer_%Y%m%d_%H%M%S"))
        if memory_limit:
            rr.spawn(memory_limit=memory_limit, hide_welcome_screen=True)
        else:
            rr.spawn(hide_welcome_screen=True)

    def send_blueprint(self, color_keys: list[str]) -> None:
        """
        Create a simple UI:
        - TimeSeries views for qpos
        - Spatial2D views for each color stream found
        """
        views: list[rrb.BlueprintLike] = []

        # Time series (states/actions for left/right arms)
        ts_origins = [
            f"{self.prefix}left_arm/states/qpos",
            f"{self.prefix}left_arm/actions/qpos",
            f"{self.prefix}right_arm/states/qpos",
            f"{self.prefix}right_arm/actions/qpos",
            f"{self.prefix}left_ee/states/qpos",
            f"{self.prefix}left_ee/actions/qpos",
            f"{self.prefix}right_ee/states/qpos",
            f"{self.prefix}right_ee/actions/qpos",
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

        # Images
        for ck in color_keys:
            views.append(
                rrb.Spatial2DView(
                    origin=f"{self.prefix}colors/{ck}",
                    time_ranges=[
                        rrb.VisibleTimeRange(
                            "idx",
                            start=rrb.TimeRangeBoundary.cursor_relative(seq=-self.window),
                            end=rrb.TimeRangeBoundary.cursor_relative(),
                        )
                    ],
                )
            )

        grid = rrb.Grid(
            contents=views,
            grid_columns=2,
            column_shares=[1, 1],
        )

        rr.send_blueprint(grid)

    def log_frame(self, fr: dict) -> None:
        rr.set_time_sequence("idx", int(fr.get("idx", 0)))

        # Log states/actions qpos as scalars
        for section_name in ("states", "actions"):
            section = fr.get(section_name, {}) or {}
            for part, info in section.items():
                if part == "body" or not info:
                    continue
                values = info.get("qpos", []) or []
                for j, val in enumerate(values):
                    rr.log(f"{self.prefix}{part}/{section_name}/qpos/{j}", rr.Scalar(float(val)))

        # Log images (colors)
        colors: dict[str, Path] = fr.get("colors", {}) or {}
        for ck, path in colors.items():
            _try_log_image(path, f"{self.prefix}colors/{ck}")

        # (Optional) depths could be logged similarly if you want later.

    def log_episode_offline(self, frames: list[dict]) -> None:
        for fr in frames:
            self.log_frame(fr)

    def log_episode_online(self, frames: list[dict], hz: float = 30.0) -> None:
        dt = 1.0 / float(hz)
        for fr in frames:
            self.log_frame(fr)
            time.sleep(dt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=str, required=True, help="Directory containing episode_XXXX folders", default="~/xr_teleoperate/teleop/utils/data")
    parser.add_argument("--episode", type=int, required=True, help="Episode index (e.g. 12 -> episode_0012)")
    parser.add_argument("--mode", type=str, choices=["offline", "online"], default="offline")
    parser.add_argument("--hz", type=float, default=30.0, help="Online mode playback rate (Hz)")
    parser.add_argument("--window", type=int, default=60, help="Visible time window size (idx units)")
    parser.add_argument("--memory-limit", type=str, default=None, help="Optional, e.g. 200MB or 1GB")
    parser.add_argument("--prefix", type=str, default="", help="Entity path prefix, e.g. offline/ or run1/")
    args = parser.parse_args()

    reader = EpisodeReader(task_dir=args.task_dir)
    frames = reader.load_index(args.episode)

    # Detect available color streams (color_0, color_1, ...)
    color_keys = sorted({k for fr in frames for k in (fr.get("colors") or {}).keys()})
    logger = RerunEpisodeLogger(prefix=args.prefix, window=args.window, memory_limit=args.memory_limit)

    # Build UI once based on what we found
    logger.send_blueprint(color_keys=color_keys)

    if args.mode == "offline":
        logger.log_episode_offline(frames)
    else:
        logger.log_episode_online(frames, hz=args.hz)


if __name__ == "__main__":
    main()
