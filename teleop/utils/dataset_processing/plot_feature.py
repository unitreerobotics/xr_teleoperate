#!/usr/bin/env python3
"""
Plot a single joint trajectory from one episode or an entire dataset.

Examples:
  python teleop/utils/dataset_processing/plot_feature.py teleop/testdata/episode_0006 --group left_arm --joint-index 0
  python teleop/utils/dataset_processing/plot_feature.py teleop/testdata/episode_0006/data.json --group left_arm --joint-name kLeftShoulderPitch
  python teleop/utils/dataset_processing/plot_feature.py teleop/testdata --group left_arm --joint-index 0 --output left_arm_joint0.png
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np


EP_RE = re.compile(r"^episode_(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def collect_episode_dirs(dataset_dir: Path) -> List[Path]:
    episodes: List[Tuple[int, Path]] = []
    for path in dataset_dir.iterdir():
        if not path.is_dir():
            continue
        match = EP_RE.match(path.name)
        if not match:
            continue
        episodes.append((int(match.group(1)), path))
    episodes.sort(key=lambda item: item[0])
    return [path for _, path in episodes]


def detect_input(path: Path) -> Tuple[str, List[Path]]:
    if path.is_file():
        if path.name != "data.json":
            raise ValueError(f"Expected a data.json file, got: {path}")
        return "episode", [path.parent]

    if not path.is_dir():
        raise ValueError(f"Path does not exist or is not supported: {path}")

    data_json = path / "data.json"
    if data_json.exists():
        return "episode", [path]

    episode_dirs = collect_episode_dirs(path)
    if episode_dirs:
        return "dataset", episode_dirs

    raise ValueError(
        f"Expected a dataset directory with episode_XXXX folders or an episode directory/data.json file: {path}"
    )


def find_first_group_info(
    episode_dirs: Sequence[Path], source: str, group: str
) -> Tuple[Optional[List[str]], int]:
    for episode_dir in episode_dirs:
        data = load_json(episode_dir / "data.json")
        joint_names_raw = data.get("info", {}).get("joint_names", {}).get(group)
        joint_names = joint_names_raw if isinstance(joint_names_raw, list) else None
        for step in data.get("data", []):
            if not isinstance(step, dict):
                continue
            section = step.get(source)
            if not isinstance(section, dict):
                continue
            group_data = section.get(group)
            if not isinstance(group_data, dict):
                continue
            qpos = group_data.get("qpos")
            if isinstance(qpos, list) and qpos:
                return joint_names, len(qpos)
    return None, 0


def resolve_joint_index(
    episode_dirs: Sequence[Path],
    source: str,
    group: str,
    joint_index: Optional[int],
    joint_name: Optional[str],
) -> Tuple[int, str]:
    joint_names, width = find_first_group_info(episode_dirs, source, group)
    if width <= 0:
        raise ValueError(f"Could not find non-empty {source}.{group}.qpos in the selected input")

    if joint_name is not None:
        if not joint_names:
            raise ValueError(
                f"--joint-name was provided, but no joint names were found for group '{group}'"
            )
        if joint_name not in joint_names:
            raise ValueError(
                f"Joint name '{joint_name}' not found in group '{group}'. Available: {joint_names}"
            )
        resolved_index = joint_names.index(joint_name)
        return resolved_index, joint_name

    if joint_index is None:
        raise ValueError("Provide either --joint-index or --joint-name")
    if joint_index < 0 or joint_index >= width:
        raise ValueError(
            f"--joint-index {joint_index} is out of range for group '{group}' with width {width}"
        )

    if joint_names and joint_index < len(joint_names):
        return joint_index, joint_names[joint_index]
    return joint_index, f"joint_{joint_index}"


def extract_joint_series(data: Dict[str, Any], source: str, group: str, joint_index: int) -> np.ndarray:
    values: List[float] = []
    for step in data.get("data", []):
        if not isinstance(step, dict):
            continue
        section = step.get(source)
        if not isinstance(section, dict):
            continue
        group_data = section.get(group)
        if not isinstance(group_data, dict):
            continue
        qpos = group_data.get("qpos")
        if not isinstance(qpos, list) or joint_index >= len(qpos):
            continue
        try:
            values.append(float(qpos[joint_index]))
        except (TypeError, ValueError):
            continue
    return np.asarray(values, dtype=float)


def build_average(traces: Iterable[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    trace_list = [trace for trace in traces if trace.size > 0]
    if not trace_list:
        return np.asarray([], dtype=int), np.asarray([], dtype=float)

    max_len = max(trace.size for trace in trace_list)
    sums = np.zeros(max_len, dtype=float)
    counts = np.zeros(max_len, dtype=int)

    for trace in trace_list:
        length = trace.size
        sums[:length] += trace
        counts[:length] += 1

    valid = counts > 0
    return np.arange(max_len, dtype=int)[valid], (sums[valid] / counts[valid])


def plot_single_episode(
    episode_dir: Path,
    source: str,
    group: str,
    joint_index: int,
    joint_label: str,
    output: Optional[Path],
    title: Optional[str],
) -> None:
    data = load_json(episode_dir / "data.json")
    series = extract_joint_series(data, source, group, joint_index)
    if series.size == 0:
        raise ValueError(
            f"No values found for {source}.{group}.qpos[{joint_index}] in episode '{episode_dir.name}'"
        )

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(np.arange(series.size), series, color="tab:blue", linewidth=2.0)
    ax.set_xlabel("Frame")
    ax.set_ylabel("Joint value")
    ax.set_title(title or f"{episode_dir.name}: {source}.{group}.{joint_label}")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=200, bbox_inches="tight")
    else:
        plt.show()
    plt.close(fig)


def plot_dataset(
    dataset_dir: Path,
    episode_dirs: Sequence[Path],
    source: str,
    group: str,
    joint_index: int,
    joint_label: str,
    output: Optional[Path],
    title: Optional[str],
) -> None:
    traces: List[np.ndarray] = []

    for episode_dir in episode_dirs:
        data = load_json(episode_dir / "data.json")
        series = extract_joint_series(data, source, group, joint_index)
        if series.size == 0:
            eprint(f"WARNING: skipping {episode_dir.name}, no values found for selected joint")
            continue
        traces.append(series)

    if not traces:
        raise ValueError(
            f"No episodes in '{dataset_dir}' contained values for {source}.{group}.qpos[{joint_index}]"
        )

    avg_x, avg_y = build_average(traces)

    fig, ax = plt.subplots(figsize=(12, 5))
    for i, series in enumerate(traces):
        label = "episodes" if i == 0 else None
        ax.plot(
            np.arange(series.size),
            series,
            color="tab:blue",
            linewidth=1.0,
            alpha=0.18,
            label=label,
        )

    ax.plot(avg_x, avg_y, color="tab:red", linewidth=2.5, label=f"average ({len(traces)} episodes)")
    ax.set_xlabel("Frame")
    ax.set_ylabel("Joint value")
    ax.set_title(title or f"{dataset_dir.name}: {source}.{group}.{joint_label}")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=200, bbox_inches="tight")
    else:
        plt.show()
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "path",
        help="Dataset directory, episode directory, or data.json file to plot from",
    )
    ap.add_argument(
        "--source",
        choices=["states", "actions"],
        default="states",
        help="Whether to plot from states or actions (default: states)",
    )
    ap.add_argument(
        "--group",
        required=True,
        help="Joint group name, for example left_arm or right_hand",
    )
    ap.add_argument(
        "--joint-index",
        type=int,
        default=None,
        help="Joint index inside the selected group",
    )
    ap.add_argument(
        "--joint-name",
        default=None,
        help="Joint name inside the selected group. Uses info.joint_names to resolve the index.",
    )
    ap.add_argument(
        "--output",
        default=None,
        help="Optional output image path. If omitted, the plot is shown interactively.",
    )
    ap.add_argument(
        "--title",
        default=None,
        help="Optional custom plot title",
    )
    args = ap.parse_args()

    if args.joint_index is None and args.joint_name is None:
        eprint("ERROR: provide either --joint-index or --joint-name")
        sys.exit(2)
    if args.joint_index is not None and args.joint_name is not None:
        eprint("ERROR: provide only one of --joint-index or --joint-name")
        sys.exit(2)

    input_path = Path(args.path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else None

    try:
        input_kind, episode_dirs = detect_input(input_path)
        joint_index, joint_label = resolve_joint_index(
            episode_dirs=episode_dirs,
            source=args.source,
            group=args.group,
            joint_index=args.joint_index,
            joint_name=args.joint_name,
        )

        if input_kind == "episode":
            plot_single_episode(
                episode_dir=episode_dirs[0],
                source=args.source,
                group=args.group,
                joint_index=joint_index,
                joint_label=joint_label,
                output=output_path,
                title=args.title,
            )
        else:
            plot_dataset(
                dataset_dir=input_path,
                episode_dirs=episode_dirs,
                source=args.source,
                group=args.group,
                joint_index=joint_index,
                joint_label=joint_label,
                output=output_path,
                title=args.title,
            )
    except ValueError as ex:
        eprint(f"ERROR: {ex}")
        sys.exit(2)


if __name__ == "__main__":
    main()
