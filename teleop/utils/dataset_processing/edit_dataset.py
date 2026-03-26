#!/usr/bin/env python3
"""
Filter episode folders episode_XXXX from a source directory into a new directory.

- Filters episodes by index range [--init, --end]
- Drops cameras by removing specified keys from step["colors"] in data.json
- Drops joint groups (e.g. right_arm) by emptying their states/actions arrays and joint_names
- Copies only referenced assets (so removed camera images are not copied)
- Writes into a NEW destination folder; source is never modified.
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


EP_RE = re.compile(r"^episode_(\d+)$")


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)

def parse_csv_set(s: Optional[str]) -> Set[str]:
    if not s:
        return set()
    return {x.strip() for x in s.split(",") if x.strip()}

def parse_csv_int_set(s: Optional[str], arg_name: str) -> Set[int]:
    if not s:
        return set()
    out: Set[int] = set()
    for raw in s.split(","):
        token = raw.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError:
            eprint(f"ERROR: {arg_name} must contain comma-separated integers, got '{token}'")
            sys.exit(2)
        if value < 0 and value not in {-1, -2}:
            eprint(
                f"ERROR: {arg_name} only allows negative sentinels -1 (odd) and -2 (even), got {value}"
            )
            sys.exit(2)
        out.add(value)
    return out

def remove_phrase_from_prompt(prompt: str, phrase: str) -> Tuple[str, int]:
    """
    Remove a phrase from a prompt (case-insensitive) and normalize whitespace.
    Returns (new_prompt, num_occurrences_removed).
    """
    pat = re.compile(re.escape(phrase), flags=re.IGNORECASE)
    new_prompt, n = pat.subn("", prompt)
    # Normalize whitespace and common punctuation spacing artifacts
    new_prompt = re.sub(r"\s+", " ", new_prompt).strip()
    new_prompt = re.sub(r"\s+([,.;:!?])", r"\1", new_prompt)
    return new_prompt, n

def find_episodes_prompt(dataset: Path, prompt: str) -> List[int]:
    """
    Return episode indices whose data.json text description contains `prompt`.
    Matching is case-insensitive across string fields in the top-level "text" object.
    """
    needle = prompt.strip().lower()
    if not needle:
        return set()

    found: Set[int] = set()
    for ep_path in dataset.iterdir():
        if not ep_path.is_dir():
            continue
        m = EP_RE.match(ep_path.name)
        if not m:
            continue
        ep_idx = int(m.group(1))
        data_path = ep_path / "data.json"
        if not data_path.exists():
            continue
        try:
            with data_path.open("r", encoding="utf-8") as f:
                dj: Dict[str, Any] = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        text_obj = dj.get("text")
        if not isinstance(text_obj, dict):
            continue

        text_strings = [v for v in text_obj.values() if isinstance(v, str)]
        if any(needle in value.lower() for value in text_strings):
            found.add(ep_idx)

    return sorted(found)

def drop_group_in_step(step: Dict[str, Any], group: str) -> None:
    """Empty the joint arrays for a group in both states and actions."""
    for section_key in ("states", "actions"):
        sec = step.get(section_key)
        if isinstance(sec, dict):
            sec.pop(group, None) # Remove entire group if exists


def collect_referenced_files(data_json: Dict[str, Any]) -> Set[str]:
    """
    Collect relative file paths referenced by the JSON.
    We include:
      - colors dict values
      - depths dict values
      - audios if dict/str (optional)
    Extend if you have more referenced assets.
    """
    refs: Set[str] = set()
    data_list = data_json.get("data", [])
    if not isinstance(data_list, list):
        return refs

    for step in data_list:
        if not isinstance(step, dict):
            continue

        for key in ("colors", "depths"):
            d = step.get(key, {})
            if isinstance(d, dict):
                for _, rel in d.items():
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Source folder containing episode_XXXX subfolders")
    ap.add_argument("--init", type=int, default=0, help="First episode index to copy (inclusive)")
    ap.add_argument("--end", type=int, default=-1, help="Last episode index to copy (inclusive) / -1 means no limit")
    ap.add_argument("--suffix", default=None, help="Suffix appended to src folder name for destination")
    ap.add_argument("--dst_parent", default=None, help="Where to create destination folder (default: parent of --src)")
    ap.add_argument("--overwrite", action="store_true", help="If destination exists, delete it first")
    ap.add_argument("--dry_run", action="store_true", help="Print what would be done without copying")

    # Drop cameras by key in step["colors"], e.g. color_0,color_1,...
    ap.add_argument(
        "--drop_cameras",
        default=None,
        help="Comma-separated color keys to DROP (e.g. color_1,color_2). Removes from data.json and skips copying those images.",
    )

    # Drop entire joint groups
    ap.add_argument(
        "--drop_joint_groups",
        default=None,
        help="Comma-separated joint groups to DROP completely (e.g. right_arm,right_ee). Clears states/actions arrays and joint_names.",
    )

    # Replace prompt 
    ap.add_argument(
        "--replace_prompt",
        default=None,
        help="String to replace dataset prompt with (for all episodes). If not set, original prompts are kept.",
    )
    ap.add_argument(
        "--index",
        default=None,
        help="Comma-separated episode indices for --replace_prompt (e.g. 1,2,3,4,5). Special values: -2=all even episodes (including 0), -1=all odd episodes.",
    )

    # Remove token prompt 
    ap.add_argument(
        "--remove_token_prompt",
        default=None,
        help="Phrase to remove from each episode prompt (text.goal). Case-insensitive. Prints episode names where phrase is not found.",
    )
    ap.add_argument(
        "--find_episodes_prompt",
        default=None,
        help="Prompt substring to find in episode text fields. When set, only matching episode_* folders are processed.",
    )
    
    args = ap.parse_args()

    src = Path(args.src).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        eprint(f"ERROR: --src is not a directory: {src}")
        sys.exit(2)

    if args.init < 0 or args.end < -1 or (args.init > args.end and args.end != -1):
        eprint(f"ERROR: invalid range init={args.init}, end={args.end}")
        sys.exit(2)

    drop_cameras = parse_csv_set(args.drop_cameras)
    drop_joint_groups = parse_csv_set(args.drop_joint_groups)
    replace_prompt = args.replace_prompt
    replace_prompt_indices = parse_csv_int_set(args.index, "--index")
    replace_even = -2 in replace_prompt_indices
    replace_odd = -1 in replace_prompt_indices
    if replace_even:
        replace_prompt_indices.discard(-2)
    if replace_odd:
        replace_prompt_indices.discard(-1)
    remove_token_prompt = args.remove_token_prompt
    find_episodes_prompt_arg = args.find_episodes_prompt
    if remove_token_prompt is not None:
        remove_token_prompt = remove_token_prompt.strip()
        if not remove_token_prompt:
            eprint("ERROR: --remove_token_prompt cannot be empty/whitespace")
            sys.exit(2)
    if find_episodes_prompt_arg is not None:
        find_episodes_prompt_arg = find_episodes_prompt_arg.strip()
        if not find_episodes_prompt_arg:
            eprint("ERROR: --find_episodes_prompt cannot be empty/whitespace")
            sys.exit(2)
        matched = find_episodes_prompt(src, find_episodes_prompt_arg)
        print(matched)
        return

    if not args.suffix:
        eprint("ERROR: --suffix is required unless --find_episodes_prompt is used")
        sys.exit(2)

    dst_parent = Path(args.dst_parent).expanduser().resolve() if args.dst_parent else src.parent
    dst = dst_parent / f"{src.name}{args.suffix}"

    # Prepare destination root
    if dst.exists():
        if args.overwrite:
            if args.dry_run:
                print(f"[DRY RUN] Would delete existing destination: {dst}")
            else:
                shutil.rmtree(dst)
        else:
            eprint(
                f"ERROR: destination already exists: {dst}\n"
                f"Use --overwrite or choose a different --suffix/--dst_parent."
            )
            sys.exit(2)

    # Collect episode folders
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

    if args.end == -1:
        args.end = episodes[-1][0]

    # Filter by range
    selected = [(i, p) for (i, p) in episodes if args.init <= i <= args.end]
    if not selected:
        eprint(f"ERROR: no episode_* folders found in range [{args.init}, {args.end}] under {src}")
        sys.exit(2)

    # Create destination root
    if args.dry_run:
        print(f"[DRY RUN] Would create destination: {dst}")
    else:
        dst.mkdir(parents=True, exist_ok=False)

    print(f"Source:      {src}")
    print(f"Destination: {dst}")
    print(f"Episodes:    {args.init}..{args.end} (inclusive): {len(selected)}")
    if drop_cameras:
        print(f"Drop colors: {sorted(drop_cameras)}")
    if drop_joint_groups:
        print(f"Drop joint groups: {sorted(drop_joint_groups)}")
    if replace_prompt:
        print(f"Replace prompt with: {replace_prompt}")
        if replace_even:
            print("Replace prompt for: all even episode indices")
        if replace_odd:
            print("Replace prompt for: all odd episode indices")
        if replace_prompt_indices:
            print(f"Replace prompt only for episode indices: {sorted(replace_prompt_indices)}")
    if remove_token_prompt:
        print(f"Remove from prompt: {remove_token_prompt}")
    print("")

    token_not_found_eps: List[str] = []
    for ep_idx, ep_path in selected:
        out_ep = dst / ep_path.name

        data_path = ep_path / "data.json"
        if not data_path.exists():
            eprint(f"ERROR: Missing data.json in {ep_path}")
            sys.exit(2)

        with data_path.open("r", encoding="utf-8") as f:
            dj: Dict[str, Any] = json.load(f)

        data_list = dj.get("data", [])
        if not isinstance(data_list, list):
            eprint(f"ERROR: data.json has no valid 'data' list in {ep_path}")
            sys.exit(2)

        # 1) Drop colors keys in each step
        if drop_cameras:
            for step in data_list:
                if not isinstance(step, dict):
                    continue
                colors = step.get("colors")
                if isinstance(colors, dict):
                    step["colors"] = {k: v for k, v in colors.items() if k not in drop_cameras}

        # 2) Drop entire joint groups in each step (states + actions)
        if drop_joint_groups:
            for step in data_list:
                if not isinstance(step, dict):
                    continue
                for group in drop_joint_groups:
                    drop_group_in_step(step, group)

            # Also update info.joint_names by clearing those groups
            info = dj.get("info", {})
            if isinstance(info, dict):
                jn = info.get("joint_names", {})
                if isinstance(jn, dict):
                    for group in drop_joint_groups:
                        if group in jn:
                            jn.pop(group, None)
                    info["joint_names"] = jn
                    dj["info"] = info
                tn = info.get("tactile_names", {})
                if isinstance(tn, dict):
                    for group in drop_joint_groups:
                        if group in tn:
                            tn.pop(group, None)
                    info["tactile_names"] = tn
                    dj["info"] = info
                    
        # 3) Replace prompt if specified
        should_replace_prompt = (
            not replace_prompt_indices and not replace_even and not replace_odd
        ) or (
            ep_idx in replace_prompt_indices
        ) or (
            replace_even and ep_idx % 2 == 0
        ) or (
            replace_odd and ep_idx % 2 == 1
        )
        if args.replace_prompt and should_replace_prompt:
            rp = dj.get("text", {}).get("goal")
            if isinstance(rp, str):
                print(f"Episode {ep_path.name}: Replacing prompt '{rp}' with '{args.replace_prompt}'")
                dj.setdefault("text", {})["goal"] = args.replace_prompt

        # 4) Remove phrase from prompt if specified
        if remove_token_prompt:
            goal = dj.get("text", {}).get("goal")
            if not isinstance(goal, str):
                token_not_found_eps.append(ep_path.name)
            else:
                new_goal, n = remove_phrase_from_prompt(goal, remove_token_prompt)
                if n == 0:
                    token_not_found_eps.append(ep_path.name)
                else:
                    print(
                        f"Episode {ep_path.name}: Removed {n} occurrence(s) of '{remove_token_prompt}' from prompt"
                    )
                    dj.setdefault("text", {})["goal"] = new_goal

        # 5) Collect referenced assets AFTER filtering (so dropped cameras won't be copied)
        refs = collect_referenced_files(dj)

        if args.dry_run:
            print(f"[DRY RUN] Episode {ep_path.name}:")
            print(f"  Would create: {out_ep}")
            print(f"  Would write filtered data.json")
            print(f"  Would copy {len(refs)} referenced asset(s)")
            continue

        out_ep.mkdir(parents=True, exist_ok=False)

        # Copy root-level files except data.json (small metadata files etc.)
        for item in ep_path.iterdir():
            if item.is_file() and item.name != "data.json":
                shutil.copy2(item, out_ep / item.name)

        # Write filtered data.json
        with (out_ep / "data.json").open("w", encoding="utf-8") as f:
            json.dump(dj, f, indent=2, ensure_ascii=False)

        # Copy only referenced assets (images/audio/depths)
        for rel in sorted(refs):
            src_file = ep_path / rel
            dst_file = out_ep / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if not src_file.exists():
                eprint(f"WARNING: referenced file missing, skipping: {src_file}")
                continue
            shutil.copy2(src_file, dst_file)

    if remove_token_prompt and token_not_found_eps:
        print(
            f"\nremove_token_prompt '{remove_token_prompt}' not found in {len(token_not_found_eps)} episode(s): "
            + ", ".join(token_not_found_eps)
        )

    if not args.dry_run:
        print("\nDone.")


if __name__ == "__main__":
    main()
