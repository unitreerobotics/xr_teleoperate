import copy

DEFAULTS = {
    "frequency": 25.0,
    "xr_mode": "hand",
    "arm": "G1_29",
    "ee": "dex3",
    "iface": "enx98fc84ec937b",
    "teleop_side": "both",
    "task_dir": "./utils/data/",
    "task_name": "retail",
    "task_desc": "----",
}

IMG_CONFIG = {
    "fps": 30,
    "head_camera_type": "realsense",
    "head_camera_image_shape": [480, 640],
    "head_camera_id_numbers": ["233622072924"],
    # Mixed wrist cameras:
    # - OpenCV uses /dev/video index (int) or "/dev/videoX" (string)
    # - RealSense uses serial number (string)
    "wrist_camera_type": ["realsense", "realsense"],
    "wrist_camera_image_shape": [480, 640],
    "wrist_camera_id_numbers": ["323622271193", "335122271374"],
}

ASPECT_RATIO_THRESHOLD = 2.0  # If the aspect ratio exceeds this value, it is considered binocular


def add_arguments(parser: object) -> None:
    parser.add_argument("--frequency", type=float, default=DEFAULTS["frequency"], help="save data's frequency")

    # basic control parameters
    parser.add_argument("--xr-mode", type=str, choices=["hand", "controller"], default=DEFAULTS["xr_mode"], help="Select XR device tracking source")
    parser.add_argument("--arm", type=str, choices=["G1_29"], default=DEFAULTS["arm"], help="Select arm controller")
    parser.add_argument("--ee", type=str, choices=["dex3"], default=DEFAULTS["ee"], help="Select end effector controller")
    parser.add_argument("--iface", type=str, default=DEFAULTS["iface"], help="Network interface for DDS")
    parser.add_argument("--teleop-side", type=str, choices=["left", "right", "both"], default=DEFAULTS["teleop_side"],
                        help="Limit teleoperation motion to one side while still recording both sides")

    # mode flags
    parser.add_argument("--motion", action="store_true", help="Enable motion control mode")
    parser.add_argument("--headless", action="store_true", help="Enable headless mode (no display)")
    parser.add_argument("--affinity", action="store_true", help="Enable high priority and set CPU affinity")
    parser.add_argument("--ipc", action="store_true", help="Enable IPC server to handle input; otherwise enable sshkeyboard")
    parser.add_argument("--record", action="store_true", help="Enable data recording")
    parser.add_argument("--task-dir", type=str, default=DEFAULTS["task_dir"], help="path to save data")
    parser.add_argument("--task-name", type=str, default=DEFAULTS["task_name"], help="task name for recording")
    parser.add_argument("--task-desc", type=str, default=DEFAULTS["task_desc"], help="task goal for recording")


def get_img_config() -> dict:
    return copy.deepcopy(IMG_CONFIG)
