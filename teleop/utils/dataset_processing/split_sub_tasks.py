#!/usr/bin/env python3
"""
Split each episode into two sub-datasets using waist/arm yaw motion:
  - pick:  align + pick + rotate
  - place: place + rotate-back

Output layout:
  <dst>/
    pick/episode_XXXX/...
    place/episode_XXXX/...

Cut frame is detected as the first stable stopped segment after the main
"pick->rotate" moving segment, i.e. the start of "place".
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EP_RE = re.compile(r"^episode_(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def iter_episode_dirs(dataset_dir: Path) -> List[Tuple[int, Path]]:
    episodes: List[Tuple[int, Path]] = []
    for p in dataset_dir.iterdir():
        if not p.is_dir():
            continue
        m = EP_RE.match(p.name)
        if not m:
            continue
        episodes.append((int(m.group(1)), p))
    episodes.sort(key=lambda x: x[0])
    return episodes


def copy_rel_file(src_ep_dir: Path, dst_ep_dir: Path, rel_path: str) -> None:
    src = src_ep_dir / rel_path
    dst = dst_ep_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return
    shutil.copy2(src, dst)


def rank_yaw_candidate(group: str, joint_name: str) -> int:
    g = group.lower()
    n = joint_name.lower()
    if "yaw" not in n:
        return 10_000
    if "waistyaw" in n or ("waist" in g and "yaw" in n):
        return 0
    if "shoulderyaw" in n:
        return 1
    if "yaw" in n and "wrist" not in n:
        return 2
    return 3


def find_yaw_joint(
    joint_names: Dict[str, Any],
    yaw_group: Optional[str],
    yaw_joint_index: Optional[int],
) -> Tuple[str, int, str]:
    if yaw_group is not None:
        names = joint_names.get(yaw_group)
        if not isinstance(names, list):
            raise ValueError(f"Requested yaw group '{yaw_group}' not found in info.joint_names")
        if yaw_joint_index is not None:
            if yaw_joint_index < 0 or yaw_joint_index >= len(names):
                raise ValueError(
                    f"--yaw-joint-index {yaw_joint_index} out of range for group "
                    f"'{yaw_group}' (len={len(names)})"
                )
            return yaw_group, yaw_joint_index, str(names[yaw_joint_index])

        for i, name in enumerate(names):
            if "yaw" in str(name).lower():
                return yaw_group, i, str(name)
        if not names:
            raise ValueError(f"Group '{yaw_group}' has no joints")
        return yaw_group, 0, str(names[0])

    if yaw_joint_index is not None:
        raise ValueError("--yaw-joint-index requires --yaw-group")

    candidates: List[Tuple[int, str, int, str]] = []
    for group, names in joint_names.items():
        if not isinstance(names, list):
            continue
        for i, name in enumerate(names):
            s = str(name)
            score = rank_yaw_candidate(group, s)
            if score < 10_000:
                candidates.append((score, str(group), i, s))

    if not candidates:
        raise ValueError("No yaw-like joint found in info.joint_names")

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    _, group, joint_idx, joint_name = candidates[0]
    return group, joint_idx, joint_name


def extract_yaw_series(
    frames: List[Dict[str, Any]],
    group: str,
    joint_idx: int,
    source: str,
) -> List[float]:
    yaw_values: List[float] = []
    for i, fr in enumerate(frames):
        src = fr.get(source)
        if not isinstance(src, dict):
            raise ValueError(f"Frame {i}: missing '{source}' section")
        group_data = src.get(group)
        if not isinstance(group_data, dict):
            raise ValueError(f"Frame {i}: '{source}.{group}' missing or invalid")
        qpos = group_data.get("qpos")
        if not isinstance(qpos, list):
            raise ValueError(f"Frame {i}: '{source}.{group}.qpos' missing or invalid")
        if joint_idx < 0 or joint_idx >= len(qpos):
            raise ValueError(
                f"Frame {i}: joint index {joint_idx} out of range in '{source}.{group}.qpos' "
                f"(len={len(qpos)})"
            )
        value = qpos[joint_idx]
        if not isinstance(value, (int, float)):
            raise ValueError(f"Frame {i}: yaw value is non-numeric: {value}")
        yaw_values.append(float(value))
    return yaw_values


def smooth_short_runs(flags: List[bool], min_run_len: int) -> List[bool]:
    if min_run_len <= 1 or not flags:
        return flags[:]

    out = flags[:]
    n = len(out)
    max_passes = 5
    for _ in range(max_passes):
        changed = False
        runs: List[Tuple[int, int, bool]] = []
        start = 0
        while start < n:
            state = out[start]
            end = start + 1
            while end < n and out[end] == state:
                end += 1
            runs.append((start, end, state))
            start = end

        for start, end, _state in runs:
            run_len = end - start
            if run_len >= min_run_len:
                continue

            left = out[start - 1] if start > 0 else None
            right = out[end] if end < n else None
            replacement: Optional[bool] = None
            if left is None and right is None:
                replacement = None
            elif left is None:
                replacement = right
            elif right is None:
                replacement = left
            elif left == right:
                replacement = left
            else:
                replacement = left

            if replacement is None:
                continue
            for i in range(start, end):
                if out[i] != replacement:
                    out[i] = replacement
                    changed = True

        if not changed:
            break

    return out


def moving_flags_from_yaw(yaw_values: List[float], threshold: float) -> List[bool]:
    n = len(yaw_values)
    if n == 0:
        return []
    if n == 1:
        return [False]

    flags = [False] * n
    first_delta = abs(yaw_values[1] - yaw_values[0])
    flags[0] = first_delta > threshold
    for i in range(1, n):
        flags[i] = abs(yaw_values[i] - yaw_values[i - 1]) > threshold
    return flags


def first_index_with_state(flags: List[bool], start: int, target: bool) -> int:
    for i in range(start, len(flags)):
        if flags[i] == target:
            return i
    return len(flags)


def bool_runs(flags: List[bool]) -> List[Tuple[int, int, bool]]:
    runs: List[Tuple[int, int, bool]] = []
    n = len(flags)
    i = 0
    while i < n:
        state = flags[i]
        j = i + 1
        while j < n and flags[j] == state:
            j += 1
        runs.append((i, j, state))
        i = j
    return runs


def detect_pick_place_cut(
    flags: List[bool],
    min_stopped_frames: int,
    min_moving_frames: int,
) -> int:
    """
    Return cut frame index where:
      [optional align moving] -> pick(stopped) -> rotate(moving) -> place(stopped)

    If stable segments are not found, fallback to basic state transitions.
    """
    n = len(flags)
    if n == 0:
        return 0

    runs = bool_runs(flags)

    # Find first stable stopped run (pick).
    pick_run_idx: Optional[int] = None
    for ri, (start, end, state) in enumerate(runs):
        if (not state) and (end - start >= min_stopped_frames):
            pick_run_idx = ri
            break

    # Find first stable moving run after pick (rotate).
    rotate_run_idx: Optional[int] = None
    if pick_run_idx is not None:
        for ri in range(pick_run_idx + 1, len(runs)):
            start, end, state = runs[ri]
            if state and (end - start >= min_moving_frames):
                rotate_run_idx = ri
                break

    # Find first stable stopped run after rotate (place start = cut frame).
    if rotate_run_idx is not None:
        for ri in range(rotate_run_idx + 1, len(runs)):
            start, end, state = runs[ri]
            if (not state) and (end - start >= min_stopped_frames):
                return start

    # Fallback to the original boundary logic: first stopped after first moving
    # after initial stopped.
    i1 = first_index_with_state(flags, 0, False)
    i2 = first_index_with_state(flags, i1, True)
    i3 = first_index_with_state(flags, i2, False)
    if i3 < n:
        return i3

    # Last fallback: split in the middle.
    return n // 2


def find_rotation_back_start(
    flags: List[bool],
    start: int,
    min_moving_frames: int,
) -> Optional[int]:
    """Find the first frame index where a stable moving run starts after `start`."""
    if start >= len(flags):
        return None

    runs = bool_runs(flags[start:])
    base = start
    for run_start, run_end, state in runs:
        if state and (run_end - run_start >= min_moving_frames):
            return base + run_start
    return None


def collect_refs_from_frame(frame: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for key in ("colors", "depths", "audios"):
        sec = frame.get(key)
        if isinstance(sec, dict):
            for rel in sec.values():
                if isinstance(rel, str) and rel:
                    refs.append(rel)
        elif isinstance(sec, str) and sec:
            refs.append(sec)
    return refs


def write_sub_episode(
    src_episode_dir: Path,
    dst_episode_dir: Path,
    episode_json: Dict[str, Any],
    frames: List[Dict[str, Any]],
    keep_idx: bool,
) -> None:
    if dst_episode_dir.exists():
        shutil.rmtree(dst_episode_dir)
    dst_episode_dir.mkdir(parents=True, exist_ok=True)
    (dst_episode_dir / "colors").mkdir(exist_ok=True)
    (dst_episode_dir / "depths").mkdir(exist_ok=True)
    (dst_episode_dir / "audios").mkdir(exist_ok=True)

    for item in src_episode_dir.iterdir():
        if item.is_file() and item.name != "data.json":
            shutil.copy2(item, dst_episode_dir / item.name)

    out_frames = copy.deepcopy(frames)
    if not keep_idx:
        for i, fr in enumerate(out_frames):
            fr["idx"] = i

    refs = set()
    for fr in out_frames:
        refs.update(collect_refs_from_frame(fr))
    for rel in sorted(refs):
        copy_rel_file(src_episode_dir, dst_episode_dir, rel)

    out_json = dict(episode_json)
    out_json["data"] = out_frames
    save_json(dst_episode_dir / "data.json", out_json)


def write_rotation_back_note(dst_episode_dir: Path, rotation_back_frame: Optional[int]) -> None:
    if rotation_back_frame is None:
        return
    note_path = dst_episode_dir / "rotation_back.txt"
    with note_path.open("w", encoding="utf-8") as f:
        f.write(f"{rotation_back_frame}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Split dataset episodes into pick(place) halves using yaw-defined cut frame."
    )
    ap.add_argument("--src", required=True, help="Source dataset directory containing episode_XXXX folders")
    ap.add_argument(
        "--dst",
        default=None,
        help="Destination root. Default: <src_parent>/<src_name>_split_sub_tasks",
    )
    ap.add_argument("--overwrite", action="store_true", help="Overwrite destination if it already exists")
    ap.add_argument("--yaw-source", choices=["states", "actions"], default="states")
    ap.add_argument("--yaw-group", default=None, help="Override yaw joint group (from info.joint_names)")
    ap.add_argument("--yaw-joint-index", type=int, default=None, help="Override yaw joint index within --yaw-group")
    ap.add_argument("--yaw-threshold", type=float, default=0.002, help="Abs delta threshold for yaw movement")
    ap.add_argument(
        "--min-state-frames",
        type=int,
        default=3,
        help="Smooth short moving/stopped runs shorter than this length (>=1)",
    )
    ap.add_argument(
        "--min-stopped-frames",
        type=int,
        default=20,
        help="Minimum frames for a stopped run to be considered stable (>=1)",
    )
    ap.add_argument(
        "--min-moving-frames",
        type=int,
        default=20,
        help="Minimum frames for a moving run to be considered stable (>=1)",
    )
    ap.add_argument("--keep-idx", action="store_true", help="Keep original frame idx; default reindexes per sub-episode")
    ap.add_argument("--dry-run", action="store_true", help="Only print planned ranges; do not write output")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.is_dir():
        eprint(f"ERROR: --src is not a directory: {src}")
        sys.exit(2)

    dst = Path(args.dst).expanduser().resolve() if args.dst else (src.parent / f"{src.name}_split_sub_tasks")
    if dst.exists() and not args.overwrite and not args.dry_run:
        eprint(f"ERROR: destination already exists: {dst} (use --overwrite)")
        sys.exit(2)

    episodes = iter_episode_dirs(src)
    if not episodes:
        eprint(f"ERROR: no episode_XXXX folders found under: {src}")
        sys.exit(2)

    if args.yaw_threshold < 0:
        eprint("--yaw-threshold must be >= 0")
        sys.exit(2)
    if args.min_state_frames < 1:
        eprint("--min-state-frames must be >= 1")
        sys.exit(2)
    if args.min_stopped_frames < 1:
        eprint("--min-stopped-frames must be >= 1")
        sys.exit(2)
    if args.min_moving_frames < 1:
        eprint("--min-moving-frames must be >= 1")
        sys.exit(2)

    sub_names = ["pick", "place"]
    sub_roots = [dst / name for name in sub_names]

    if args.dry_run:
        print(f"[DRY RUN] Source: {src}")
        print(f"[DRY RUN] Destination: {dst}")
    else:
        if dst.exists() and args.overwrite:
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)

    print(f"Source: {src}")
    print(f"Destination: {dst}")
    print(f"Episodes: {len(episodes)}")
    print(
        "Yaw detection: "
        f"source={args.yaw_source}, threshold={args.yaw_threshold}, min_state_frames={args.min_state_frames}"
    )
    print(
        "Cut detection: "
        f"min_stopped_frames={args.min_stopped_frames}, min_moving_frames={args.min_moving_frames}"
    )
    if args.yaw_group is not None:
        print(
            "Yaw override: "
            f"group={args.yaw_group}, joint_index={args.yaw_joint_index if args.yaw_joint_index is not None else 'auto'}"
        )
    print("")

    for ep_idx, ep_dir in episodes:
        data_path = ep_dir / "data.json"
        if not data_path.exists():
            eprint(f"Skipping {ep_dir.name}: missing data.json")
            continue

        try:
            episode_json = load_json(data_path)
            frames = episode_json.get("data", [])
            if not isinstance(frames, list):
                raise ValueError("data.json['data'] is not a list")

            info = episode_json.get("info", {})
            if not isinstance(info, dict):
                raise ValueError("data.json['info'] is not a dict")
            joint_names = info.get("joint_names", {})
            if not isinstance(joint_names, dict):
                raise ValueError("data.json['info']['joint_names'] is not a dict")

            yaw_group, yaw_joint_idx, yaw_joint_name = find_yaw_joint(
                joint_names=joint_names,
                yaw_group=args.yaw_group,
                yaw_joint_index=args.yaw_joint_index,
            )
            yaw_values = extract_yaw_series(
                frames=frames,
                group=yaw_group,
                joint_idx=yaw_joint_idx,
                source=args.yaw_source,
            )

            flags = moving_flags_from_yaw(yaw_values, args.yaw_threshold)
            flags = smooth_short_runs(flags, args.min_state_frames)
            cut_idx = detect_pick_place_cut(
                flags=flags,
                min_stopped_frames=args.min_stopped_frames,
                min_moving_frames=args.min_moving_frames,
            )
            rotation_back_global = find_rotation_back_start(
                flags=flags,
                start=cut_idx,
                min_moving_frames=args.min_moving_frames,
            )
        except Exception as exc:
            eprint(f"Skipping {ep_dir.name}: {exc}")
            continue

        n_frames = len(frames)
        cut_idx = max(1, min(cut_idx, n_frames - 1))
        if rotation_back_global is not None:
            rotation_back_global = max(cut_idx, min(rotation_back_global, n_frames - 1))
        rotation_back_sub = (
            rotation_back_global - cut_idx if rotation_back_global is not None else None
        )

        print(
            f"{ep_dir.name} | yaw={yaw_group}[{yaw_joint_idx}] '{yaw_joint_name}' | "
            f"cut_frame={cut_idx} (pick:0-{cut_idx - 1}, place:{cut_idx}-{n_frames - 1})"
            + (
                f" | rotation_back={rotation_back_global} (sub={rotation_back_sub})"
                if rotation_back_global is not None
                else ""
            )
        )

        if args.dry_run:
            continue

        ranges = [(0, cut_idx), (cut_idx, n_frames)]
        for i, (start, end) in enumerate(ranges, start=1):
            out_ep_dir = sub_roots[i - 1] / ep_dir.name
            sliced_frames = frames[start:end]
            if not sliced_frames:
                continue
            write_sub_episode(
                src_episode_dir=ep_dir,
                dst_episode_dir=out_ep_dir,
                episode_json=episode_json,
                frames=sliced_frames,
                keep_idx=args.keep_idx,
            )

            # If this is the place subtask, write a note about when rotation-back begins.
            if i == 2:
                write_rotation_back_note(out_ep_dir, rotation_back_sub)

    if args.dry_run:
        print("\n[DRY RUN] Completed.")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()
