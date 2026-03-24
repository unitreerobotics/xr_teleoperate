# Dataset Processing Scripts

This folder contains utilities for editing, splitting, merging, augmenting, and replaying dataset episodes. By order of relevance, the available scripts are the following:


## `replay_dataset.py`
Purpose: Interactive Rerun viewer for navigating episodes in a dataset. Allows you to visualize, one-by-one, several episodes from a dataset.

Example:
```bash
python utils/replay_dataset.py --task-dir /mnt/sata1/xr_teleoperate_datasets/restock_yaw/ --start 1 --memory-limit 2000MB
```

Flags:
- `--task-dir` (required): Directory containing `episode_XXXX`.
- `--start` (default: first available): Initial episode index.
- `--window` (default: `60`): Visible timeline window length.
- `--memory-limit` (default: `None`): Optional Rerun memory cap.
- `--playback` (default: `offline`): `offline` or `online`.
- `--hz` (default: `30.0`): Playback rate in online mode.


## `cut_multiple_episodes.py`
Purpose: Apply multiple cuts (frame ranges) across several episodes, each overwritten in place.

Example:
```bash
python utils/dataset_processing/cut_multiple_episodes.py --task-dir utils/data/task_001 --cuts "[(12, 0, -1), (13, 10, 50)]"
```

Flags:
- `--task-dir` (required): Directory containing `episode_XXXX`.
- `--cuts` (required): Python-literal list of tuples `[(episode, start, end), ...]`. Use `-1` for end-of-episode.
- `--keep-idx`: Keep original frame `idx` values (otherwise reindex to `0..N-1`).


## `merge_datasets.py`
Purpose: Merge two or more dataset directories into a single output dataset with sequential episode numbering.

Example:
```bash
python utils/dataset_processing/merge_datasets.py utils/data/task_001 utils/data/task_002 -o utils/data/task_001_task_002_merged --start-index 0 --padding 4
```

Arguments and flags:
- `datasets` (positional, required): Input dataset directories.
- `-o`, `--output` (default: inferred from input names): Output dataset directory.
- `--padding` (default: `4`): Zero-padding width for output episode names.
- `--start-index` (default: `0`): Starting output episode index.
- `--dry-run`: Print planned actions without copying.


## `augment_dataset.py`
Purpose: Randomly sample episodes and apply brightness/contrast jitter to color images, writing to a new dataset folder.

Example:
```bash
python utils/dataset_processing/augment_dataset.py --src utils/data/task_001 --out_name task_001_aug --brightness 25 --contrast 20 --sample_ratio 0.5 --seed 42
```

Flags:
- `--src` (required): Source folder with `episode_XXXX` subfolders.
- `--out_name` (required): Name of output folder created next to `--src`.
- `--brightness` (default: `30.0`): Max brightness jitter percentage (`[-v, +v]`).
- `--contrast` (default: `30.0`): Max contrast jitter percentage (`[-v, +v]`).
- `--sample_ratio` (default: `1.0`): Fraction of episodes to sample.
- `--sample_num` (default: `None`): Number of episodes to sample (overrides `--sample_ratio`).
- `--seed` (default: `None`): Random seed.
- `--overwrite`: Delete destination first if it exists.
- `--dry_run`: Print planned actions without writing files.


## `edit_dataset.py`
Purpose: Copy a filtered dataset into a new folder, with optional camera removal, joint-group removal, and prompt replacement.

Example:
```bash
python utils/dataset_processing/edit_dataset.py --src utils/data/task_001 --init 0 --end 100 --suffix _filtered --drop_cameras color_2 --drop_joint_groups right_arm --replace_prompt "pick up the cube"
```

Flags:
- `--src` (required): Source folder with `episode_XXXX` subfolders.
- `--init` (default: `0`): First episode index to include (inclusive).
- `--end` (default: `-1`): Last episode index to include (inclusive), `-1` means no upper limit.
- `--suffix` (required): Suffix appended to source dataset folder name for destination.
- `--dst_parent` (default: parent of `--src`): Destination parent directory.
- `--overwrite`: Delete destination first if it exists.
- `--dry_run`: Print planned actions without writing files.
- `--drop_cameras`: Comma-separated `colors` keys to remove (for example `color_1,color_2`).
- `--drop_joint_groups`: Comma-separated joint groups to remove from `states/actions` and metadata.
- `--replace_prompt`: Replace `text.goal` prompt string in every selected episode.


## `cut_episode.py`
Purpose: Cut one episode into a frame range and write to a target episode folder (or replace in place).

Example:
```bash
python utils/dataset_processing/cut_episode.py --task-dir utils/data/task_001 --episode 12 --start 100 --end 300 --out-episode 1012
```

Flags:
- `--task-dir` (required): Directory containing `episode_XXXX`.
- `--episode` (required): Source episode index.
- `--start` (required): Start frame index (inclusive).
- `--end` (default: end of episode): End frame index (exclusive).
- `--out-episode` (default: same as source): Output episode index.
- `--keep-idx`: Keep original frame `idx` values (otherwise reindex to `0..N-1`).

## `replay_episode.py`
Purpose: Visualize one episode in Rerun (offline or real-time playback).

Example:
```bash
python utils/dataset_processing/replay_episode.py --task-dir utils/data/task_001 --episode 12 --mode online --hz 30 --window 60 --memory-limit 500MB
```

Flags:
- `--task-dir` (required): Directory containing `episode_XXXX`.
- `--episode` (required): Episode index to replay.
- `--mode` (default: `offline`): `offline` or `online`.
- `--hz` (default: `30.0`): Playback rate in online mode.
- `--window` (default: `60`): Visible timeline window length.
- `--memory-limit` (default: `None`): Optional Rerun memory cap (for example `200MB`, `1GB`).
- `--prefix` (default: empty): Entity path prefix in Rerun.

## `split_sub_tasks.py`
Purpose: Split each episode into two datasets (`pick` and `place`) using yaw-motion-based cut detection.

**Note:** This script is adjusted for one-specific dataset, so most probably it does not apply to many cases.

Example:
```bash
python utils/dataset_processing/split_sub_tasks.py --src utils/data/task_001 --dst utils/data/task_001_split --yaw-source states --yaw-threshold 0.002 --min-stopped-frames 20 --min-moving-frames 20
```

Flags:
- `--src` (required): Source dataset directory with `episode_XXXX`.
- `--dst` (default: `<src_parent>/<src_name>_split_sub_tasks`): Output root directory.
- `--overwrite`: Overwrite destination if it exists.
- `--yaw-source` (default: `states`): Source for yaw values (`states` or `actions`).
- `--yaw-group` (default: `None`): Override yaw joint group.
- `--yaw-joint-index` (default: `None`): Override yaw joint index (requires `--yaw-group`).
- `--yaw-threshold` (default: `0.002`): Absolute delta threshold for movement detection.
- `--min-state-frames` (default: `3`): Smoothing threshold for short moving/stopped runs.
- `--min-stopped-frames` (default: `20`): Minimum stable stopped-run length.
- `--min-moving-frames` (default: `20`): Minimum stable moving-run length.
- `--keep-idx`: Keep original frame `idx` values in output.
- `--dry-run`: Print cut ranges and actions without writing output.

## `plot_feature.py`
Purpose: Plot one joint trajectory from either a single episode or a full dataset. For dataset plots, each episode is shown with a faint line and the dataset average is overlaid.

Examples:
```bash
python teleop/utils/dataset_processing/plot_feature.py teleop/testdata/episode_0006 --group left_arm --joint-index 0
python teleop/utils/dataset_processing/plot_feature.py teleop/testdata/episode_0006/data.json --group left_arm --joint-name kLeftShoulderPitch
python teleop/utils/dataset_processing/plot_feature.py teleop/testdata --group left_arm --joint-index 0 --output left_arm_joint0.png
```

Arguments and flags:
- `path` (positional, required): Dataset directory, episode directory, or `data.json` file.
- `--source` (default: `states`): Plot from `states` or `actions`.
- `--group` (required): Joint group name, for example `left_arm`.
- `--joint-index`: Joint index inside the selected group.
- `--joint-name`: Joint name inside the selected group. Uses `info.joint_names` to resolve the index.
- `--output` (default: interactive window): Save plot to an image file instead of opening a window.
- `--title` (default: auto): Custom plot title.

