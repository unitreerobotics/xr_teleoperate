#!/usr/bin/env python3
"""
Interactive dataset viewer for Rerun.

- Spawns a Rerun viewer on the first available port (starting at 9876).
- If another viewer is already running, this starts a separate instance.
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
import gc
import argparse
import re
from bisect import bisect_left
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
    def __init__(
        self,
        window: int = 60,
        memory_limit: str | None = None,
        viewer_port: int = 9876,
        port_scan: int = 64,
    ):
        self.window = window

        rr.init(datetime.now().strftime("DatasetViewer_%Y%m%d_%H%M%S"))
        self.viewer_port = self._pick_available_port(start_port=viewer_port, max_tries=port_scan)

        spawn_kwargs = {
            "port": self.viewer_port,
            "hide_welcome_screen": True,
        }
        if memory_limit:
            rr.spawn(memory_limit=memory_limit, hide_welcome_screen=True)
        else:
            rr.spawn(hide_welcome_screen=True)

        self._current_episode: int | None = None
        self._current_color_keys: list[str] = []
        self._active_timeline = "idx"
        self._timeline_counter = 0

    @staticmethod
    def _ep_prefix(ep: int) -> str:
        return f"episode_{ep:04d}/"

    def _window_time_range(self) -> rrb.VisibleTimeRange:
        return rrb.VisibleTimeRange(
            self._active_timeline,
            start=rrb.TimeRangeBoundary.cursor_relative(seq=-self.window),
            end=rrb.TimeRangeBoundary.cursor_relative(),
        )

    def send_blueprint(self, ep: int, color_keys: list[str]) -> None:
        """Update UI to focus on a specific episode prefix."""
        prefix = self._ep_prefix(ep)
        views: list[rrb.BlueprintLike] = []
        top_row_colors = [ck for ck in ("color_0", "color_1", "color_2") if ck in color_keys]
        top_row_color_set = set(top_row_colors)
        has_color0 = "color_0" in top_row_color_set

        for ck in top_row_colors:
            views.append(
                rrb.Spatial2DView(
                    origin=f"{prefix}colors/{ck}",
                    time_ranges=[self._window_time_range()],
                )
            )

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
                    time_ranges=[self._window_time_range()],
                    plot_legend=rrb.PlotLegend(visible=True),
                )
            )

        # Remaining images
        for ck in color_keys:
            if ck in top_row_color_set:
                continue
            views.append(
                rrb.Spatial2DView(
                    origin=f"{prefix}colors/{ck}",
                    time_ranges=[self._window_time_range()],
                )
            )

        grid_columns = 3
        num_rows = max((len(views) + grid_columns - 1) // grid_columns, 1)
        row_shares = [1] * num_rows
        if has_color0:
            row_shares[0] = 3

        column_shares = [1, 1, 1]
        if has_color0:
            # Make color_0 (top-left tile) wider than color_1/color_2.
            column_shares = [3, 1, 1]

        rr.send_blueprint(
            rrb.Grid(
                contents=views,
                grid_columns=grid_columns,
                column_shares=column_shares,
                row_shares=row_shares,
            )
        )

    def _log_frame(self, ep: int, fr: dict) -> int:
        prefix = self._ep_prefix(ep)
        local_idx = int(fr.get("idx", 0))
        rr.set_time_sequence(self._active_timeline, local_idx)

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
        return local_idx

    def _clear_episode_entities(self, ep: int) -> None:
        """
        Best-effort clear of an episode subtree in rerun.
        This keeps only the active episode visible and helps bound memory.
        """
        clear_cls = getattr(rr, "Clear", None)
        if clear_cls is None:
            return
        entity_path = self._ep_prefix(ep).rstrip("/")
        try:
            rr.log(entity_path, clear_cls(recursive=True))
        except Exception:
            pass

    def switch_episode(
        self,
        reader: EpisodeReader,
        ep: int,
        playback: str = "offline",
        hz: float = 30.0,
    ) -> tuple[list[str], int]:
        """
        Load and log one episode at a time.
        When switching episodes, previous in-process data is released.
        """
        if self._current_episode == ep:
            return self._current_color_keys, -1

        prev_episode = self._current_episode
        frames = reader.load_index(ep)
        if not frames:
            raise RuntimeError(f"Episode {ep} has no frames yet.")
        color_keys = sorted({k for fr in frames for k in (fr.get("colors") or {}).keys()})
        self._timeline_counter += 1
        self._active_timeline = f"idx_ep_{ep:04d}_{self._timeline_counter}"
        max_local_idx = -1

        if playback == "online":
            dt = 1.0 / float(hz)
            for fr in frames:
                max_local_idx = max(max_local_idx, self._log_frame(ep, fr))
                time.sleep(dt)
        else:
            for fr in frames:
                max_local_idx = max(max_local_idx, self._log_frame(ep, fr))

        frame_count = len(frames)
        self._current_episode = ep
        self._current_color_keys = color_keys
        active_end_idx = max(max_local_idx, 0)
        rr.set_time_sequence(self._active_timeline, active_end_idx)
        rr.log(f"{self._ep_prefix(ep)}_switch_marker", rr.Scalar(float(ep)))
        if prev_episode is not None and prev_episode != ep:
            self._clear_episode_entities(prev_episode)
        del frames
        gc.collect()
        return color_keys, frame_count


def list_episodes(task_dir: Path) -> list[int]:
    """Return available episode indices by scanning episode_<digits> folders."""
    eps: list[int] = []
    pat = re.compile(r"episode_(\d+)$")
    for p in task_dir.iterdir():
        if not p.is_dir():
            continue
        m = pat.match(p.name)
        if m:
            eps.append(int(m.group(1)))
    return sorted(eps)


def refresh_episode_cursor(task_dir: Path, current_ep: int | None) -> tuple[list[int], int]:
    """
    Reload episode list and return a valid cursor index close to current_ep.
    This allows interactive navigation to discover newly added episodes.
    """
    eps = list_episodes(task_dir)
    if not eps:
        raise RuntimeError(f"No episode_<digits> folders found under: {task_dir}")

    if current_ep is None:
        return eps, 0

    if current_ep in eps:
        return eps, eps.index(current_ep)

    insert_pos = bisect_left(eps, current_ep)
    cur_idx = min(max(insert_pos, 0), len(eps) - 1)
    return eps, cur_idx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=str, required=True)
    parser.add_argument("--start", type=int, default=None, help="Start episode index (e.g. 12)")
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--memory-limit", type=str, default=None, help="e.g. 200MB or 1GB")
    parser.add_argument("--viewer-port", type=int, default=9876, help="Preferred Rerun viewer port")
    parser.add_argument(
        "--viewer-port-scan",
        type=int,
        default=64,
        help="How many ports to scan upward if preferred port is busy",
    )
    parser.add_argument("--playback", choices=["offline", "online"], default="offline")
    parser.add_argument("--hz", type=float, default=30.0)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).expanduser()
    eps = list_episodes(task_dir)
    if not eps:
        raise RuntimeError(f"No episode_<digits> folders found under: {task_dir}")

    # Choose initial episode
    if args.start is not None:
        if args.start not in eps:
            raise RuntimeError(f"--start {args.start} not found. Available range: {eps[0]}..{eps[-1]}")
        cur_idx = eps.index(args.start)
    else:
        cur_idx = 0
    cur_ep = eps[cur_idx]

    reader = EpisodeReader(task_dir=str(task_dir))
    viewer = RerunDatasetViewer(
        window=args.window,
        memory_limit=args.memory_limit,
        viewer_port=args.viewer_port,
        port_scan=args.viewer_port_scan,
    )
    if viewer.viewer_port > 0:
        print(f"Rerun viewer port: {viewer.viewer_port}")

    def show_episode(ep: int) -> bool:
        try:
            color_keys, frame_count = viewer.switch_episode(
                reader,
                ep,
                playback=args.playback,
                hz=args.hz,
            )
        except Exception as exc:
            print(f"\nFailed to show episode {ep} (episode_{ep:04d}): {exc}")
            return False

        viewer.send_blueprint(ep, color_keys=color_keys)
        print(f"\nNow showing episode {ep}  (folder episode_{ep:04d})")
        if frame_count >= 0:
            print(f"Loaded {frame_count} frames. Previous episode data released from local memory.")
        return True

    # Show first
    show_episode(cur_ep)

    # Interactive loop
    print("\nCommands: n=next, p=prev, <number>=jump to episode, q=quit\n")
    while True:
        cmd = input("viewer> ").strip().lower()
        if cmd in ("q", "quit", "exit"):
            break
        elif cmd in ("n", "next"):
            eps, cur_idx = refresh_episode_cursor(task_dir, cur_ep)
            next_idx = min(cur_idx + 1, len(eps) - 1)
            next_ep = eps[next_idx]
            if show_episode(next_ep):
                cur_idx = next_idx
                cur_ep = next_ep
        elif cmd in ("p", "prev", "previous"):
            eps, cur_idx = refresh_episode_cursor(task_dir, cur_ep)
            prev_idx = max(cur_idx - 1, 0)
            prev_ep = eps[prev_idx]
            if show_episode(prev_ep):
                cur_idx = prev_idx
                cur_ep = prev_ep
        elif cmd.isdigit():
            eps, _ = refresh_episode_cursor(task_dir, cur_ep)
            ep = int(cmd)
            if ep not in eps:
                print(f"Episode {ep} not found. Available range: {eps[0]}..{eps[-1]}")
                continue
            jump_idx = eps.index(ep)
            jump_ep = eps[jump_idx]
            if show_episode(jump_ep):
                cur_idx = jump_idx
                cur_ep = jump_ep
        else:
            print("Unknown command. Use: n, p, <number>, q")


if __name__ == "__main__":
    main()
