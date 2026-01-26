#!/usr/bin/env python3
"""
Randomly sample episodes from a dataset and augment color images with
brightness/contrast jitter. Writes into a NEW destination folder.
"""

import argparse
import json
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import cv2
import numpy as np


EP_RE = re.compile(r"^episode_(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def collect_color_files(data_json: Dict[str, Any]) -> Set[str]:
    refs: Set[str] = set()
    data_list = data_json.get("data", [])
    if not isinstance(data_list, list):
        return refs
    for step in data_list:
        if not isinstance(step, dict):
            continue
        colors = step.get("colors", {})
        if isinstance(colors, dict):
            for _, rel in colors.items():
                if isinstance(rel, str) and rel:
                    refs.add(rel)
    return refs


def collect_other_files(data_json: Dict[str, Any]) -> Set[str]:
    refs: Set[str] = set()
    data_list = data_json.get("data", [])
    if not isinstance(data_list, list):
        return refs
    for step in data_list:
        if not isinstance(step, dict):
            continue
        depths = step.get("depths", {})
        if isinstance(depths, dict):
            for _, rel in depths.items():
                if isinstance(rel, str) and rel:
                    refs.add(rel)
        aud = step.get("audios", None)
        if isinstance(aud, dict):
            for _, rel in aud.items():
                if isinstance(rel, str) and rel:
                    refs.add(rel)
        elif isinstance(aud, str) and aud:
            refs.add(aud)
    return refs


def apply_brightness_contrast(
    img: np.ndarray, brightness_pct: float, contrast_pct: float
) -> np.ndarray:
    img_f = img.astype(np.float32)
    if brightness_pct != 0:
        img_f *= 1.0 + (brightness_pct / 100.0)
    if contrast_pct != 0:
        img_f = (img_f - 127.5) * (1.0 + (contrast_pct / 100.0)) + 127.5
    return np.clip(img_f, 0, 255).astype(np.uint8)


def pick_episodes(
    episodes: List[Tuple[int, Path]],
    rng: random.Random,
    sample_ratio: float,
    sample_num: Optional[int],
) -> List[Tuple[int, Path]]:
    if sample_num is not None:
        if sample_num <= 0:
            return []
        if sample_num >= len(episodes):
            return episodes
        return rng.sample(episodes, sample_num)

    if sample_ratio >= 1.0:
        return episodes
    if sample_ratio <= 0.0:
        return []
    return [ep for ep in episodes if rng.random() < sample_ratio]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Source folder containing episode_XXXX subfolders")
    ap.add_argument("--out_name", required=True, help="Name of output folder (created next to --src)")
    ap.add_argument(
        "--brightness",
        type=float,
        default=10.0,
        help="Max brightness jitter percentage (random in [-val, +val])",
    )
    ap.add_argument(
        "--contrast",
        type=float,
        default=0.0,
        help="Max contrast jitter percentage (random in [-val, +val])",
    )
    ap.add_argument(
        "--sample_ratio",
        type=float,
        default=1.0,
        help="Fraction of episodes to randomly sample (0..1)",
    )
    ap.add_argument(
        "--sample_num",
        type=int,
        default=None,
        help="Number of episodes to randomly sample (overrides --sample_ratio)",
    )
    ap.add_argument("--seed", type=int, default=None, help="Random seed")
    ap.add_argument("--overwrite", action="store_true", help="If destination exists, delete it first")
    ap.add_argument("--dry_run", action="store_true", help="Print what would be done without copying")
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        eprint(f"ERROR: --src is not a directory: {src}")
        sys.exit(2)

    dst = src.parent / args.out_name
    if dst.exists():
        if args.overwrite:
            if args.dry_run:
                print(f"[DRY RUN] Would delete existing destination: {dst}")
            else:
                shutil.rmtree(dst)
        else:
            eprint(
                f"ERROR: destination already exists: {dst}\n"
                f"Use --overwrite or choose a different --out_name."
            )
            sys.exit(2)

    episodes: List[Tuple[int, Path]] = []
    for p in src.iterdir():
        if not p.is_dir():
            continue
        m = EP_RE.match(p.name)
        if not m:
            continue
        idx = int(m.group(1))
        episodes.append((idx, p))
    episodes.sort(key=lambda t: t[0])
    if not episodes:
        eprint(f"ERROR: no episode_* folders found under {src}")
        sys.exit(2)

    rng = random.Random(args.seed)
    selected = pick_episodes(episodes, rng, args.sample_ratio, args.sample_num)
    if not selected:
        eprint("ERROR: no episodes selected (check --sample_ratio/--sample_num)")
        sys.exit(2)

    if args.dry_run:
        print(f"[DRY RUN] Would create destination: {dst}")
    else:
        dst.mkdir(parents=True, exist_ok=False)

    print(f"Source:      {src}")
    print(f"Destination: {dst}")
    print(f"Episodes:    {len(selected)} / {len(episodes)}")
    print(f"Brightness jitter: +/-{abs(args.brightness)}%")
    print(f"Contrast jitter:   +/-{abs(args.contrast)}%")
    print("")

    for ep_idx, ep_path in selected:
        out_ep = dst / ep_path.name
        data_path = ep_path / "data.json"
        if not data_path.exists():
            eprint(f"ERROR: Missing data.json in {ep_path}")
            sys.exit(2)

        with data_path.open("r", encoding="utf-8") as f:
            dj: Dict[str, Any] = json.load(f)

        color_refs = collect_color_files(dj)
        other_refs = collect_other_files(dj)

        if args.dry_run:
            print(f"[DRY RUN] Episode {ep_path.name}:")
            print(f"  Would copy episode folder to: {out_ep}")
            print(f"  Would adjust {len(color_refs)} color image(s)")
            continue

        shutil.copytree(ep_path, out_ep)

        for rel in sorted(color_refs):
            src_file = out_ep / rel
            if not src_file.exists():
                eprint(f"WARNING: referenced color file missing, skipping: {src_file}")
                continue
            img = cv2.imread(str(src_file), cv2.IMREAD_COLOR)
            if img is None:
                eprint(f"WARNING: failed to read image, skipping: {src_file}")
                continue
            b_jitter = rng.uniform(-abs(args.brightness), abs(args.brightness))
            c_jitter = rng.uniform(-abs(args.contrast), abs(args.contrast))
            out = apply_brightness_contrast(img, b_jitter, c_jitter)
            if not cv2.imwrite(str(src_file), out):
                eprint(f"WARNING: failed to write image, skipping: {src_file}")

        for rel in sorted(other_refs):
            src_file = out_ep / rel
            if not src_file.exists():
                eprint(f"WARNING: referenced file missing, skipping: {src_file}")

    if not args.dry_run:
        print("\nDone.")


if __name__ == "__main__":
    main()
