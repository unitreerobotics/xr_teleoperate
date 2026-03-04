import ctypes
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# 把你 conda 环境里的新版 libstdc++ 提前塞进进程，全局可见
# ctypes.CDLL("/opt/miniconda3/envs/xr_tele/lib/libstdc++.so.6", mode=ctypes.RTLD_GLOBAL)


import numpy as np
import time
import argparse
import cv2
from multiprocessing import shared_memory, Value, Array, Lock
import threading
import logging_mp
logging_mp.basic_config(level=logging_mp.INFO)
logger_mp = logging_mp.get_logger(__name__)

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from televuer import TeleVuerWrapper
from teleop.robot_control.robot_arm import G1_29_ArmController, G1_23_ArmController, H1_2_ArmController, H1_ArmController
from teleop.robot_control.robot_arm_ik import G1_29_ArmIK, G1_23_ArmIK, H1_2_ArmIK, H1_ArmIK
from teleop.robot_control.robot_hand_unitree import Dex3_1_Controller
from teleop.robot_control.robot_hand_inspire import Inspire_Controller
from teleop.robot_control.robot_hand_brainco import Brainco_Controller
from teleop.image_server.image_client import ImageClient
from teleop.utils.episode_writer import EpisodeWriter
from teleop.utils.ipc import IPC_Server
from sshkeyboard import listen_keyboard, stop_listening

from dex_dds_helper import DexDDSTeleopHelper
from teleop.robot_control.robot_hand_unitree import Dex3_1_Right_JointIndex, Dex3_1_Left_JointIndex
from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_, HandState_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__HandCmd_
# for gripper

# for simulation
from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_


def _redirect_cyclonedds_trace_log() -> None:
    """
    unitree_sdk2py hardcodes CycloneDDS trace output to /tmp/cdds.LOG when --iface is used.
    Some environments deny writes to /tmp for this process, so redirect to local writable path.
    """
    try:
        import unitree_sdk2py.core.channel as _dds_channel
        cfg = getattr(_dds_channel, "ChannelConfigHasInterface", None)
        if isinstance(cfg, str) and "/tmp/cdds.LOG" in cfg:
            local_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cdds.LOG")
            setattr(_dds_channel, "ChannelConfigHasInterface", cfg.replace("/tmp/cdds.LOG", local_log))
            logger_mp.info(f"[dds] Redirect CycloneDDS trace log to: {local_log}")
    except Exception as e:
        logger_mp.warning(f"[dds] Failed to patch CycloneDDS trace log path: {e}")

def publish_reset_category(category: int,publisher): # Scene Reset signal
    msg = String_(data=str(category))
    publisher.Write(msg)
    # logger_mp.info(f"published reset category: {category}")

# state transition
START          = False  # Enable to start robot following VR user motion  
STOP           = False  # Enable to begin system exit procedure
RECORD_TOGGLE  = False  # [Ready] ⇄ [Recording] ⟶ [AutoSave] ⟶ [Ready]         (⇄ manual) (⟶ auto)
RECORD_RUNNING = False  # True if [Recording]
RECORD_READY   = True   # True if [Ready], False if [Recording] / [AutoSave]
# task info
TASK_NAME = None
TASK_DESC = None
ITEM_ID = None

# multi-task selection (local prompts)
TASKS = []
TASK_IDX = 0
TASK_IDX_INPUT = ""
TASK_IDX_INPUT_LAST_TS = 0.0
BASE_TASK_NAME = None

def _normalize_task(entry: Any, idx: int) -> Dict[str, Any]:
    if isinstance(entry, str):
        prompt = entry.strip()
        if not prompt:
            raise ValueError(f"tasks[{idx}] is empty")
        return {"task_name": f"task_{idx}", "task_desc": prompt}
    if isinstance(entry, dict):
        task_name = entry.get("task_name") or entry.get("name") or entry.get("id") or f"task_{idx}"
        task_desc = (
            entry.get("task_desc")
            or entry.get("prompt")
            or entry.get("goal")
            or entry.get("text")
            or entry.get("desc")
        )
        if not isinstance(task_desc, str) or not task_desc.strip():
            raise ValueError(f"tasks[{idx}] missing prompt (expected one of: task_desc/prompt/goal/text/desc)")
        out = {"task_name": str(task_name), "task_desc": task_desc.strip()}
        task_long_desc = entry.get("description") or entry.get("task_long_desc")
        if isinstance(task_long_desc, str) and task_long_desc.strip():
            out["task_long_desc"] = task_long_desc.strip()
        task_steps = entry.get("steps")
        if isinstance(task_steps, str) and task_steps.strip():
            out["steps"] = task_steps.strip()
        item_id = entry.get("item_id")
        if item_id is not None:
            out["item_id"] = item_id
        return out
    raise ValueError(f"tasks[{idx}] must be a string or object, got: {type(entry).__name__}")

def load_tasks(tasks_file: Optional[str], inline_prompts: Optional[List[str]], default_task_name: str, default_task_desc: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []

    if tasks_file:
        path = Path(tasks_file).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"--tasks-file not found: {path}")
        content = path.read_text(encoding="utf-8")
        stripped = content.lstrip()
        is_json_like = stripped.startswith("[") or stripped.startswith("{")
        if is_json_like:
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                logger_mp.warning(f"--tasks-file looks like JSON but failed to parse; treating as newline prompts: {path}")
                data = None
        else:
            data = None

        if data is not None:
            if isinstance(data, dict) and "tasks" in data:
                data = data["tasks"]
            if not isinstance(data, list):
                raise ValueError(f"--tasks-file JSON must be a list (or dict with key 'tasks'), got: {type(data).__name__}")
            for i, entry in enumerate(data):
                tasks.append(_normalize_task(entry, i))
        else:
            lines = [ln.strip() for ln in content.splitlines()]
            prompts = [ln for ln in lines if ln and not ln.startswith("#")]
            for i, prompt in enumerate(prompts):
                tasks.append({"task_name": f"task_{i}", "task_desc": prompt})

    if inline_prompts:
        for prompt in inline_prompts:
            if not isinstance(prompt, str) or not prompt.strip():
                continue
            tasks.append({"task_name": f"task_{len(tasks)}", "task_desc": prompt.strip()})

    if not tasks:
        tasks = [{"task_name": default_task_name, "task_desc": default_task_desc}]

    return tasks

def get_selected_task() -> Dict[str, Any]:
    global TASKS, TASK_IDX
    if not TASKS:
        return {"task_name": "task_0", "task_desc": ""}
    return TASKS[TASK_IDX % len(TASKS)]

def set_task_idx(new_idx: int) -> None:
    global TASK_IDX, TASKS, TASK_IDX_INPUT, TASK_IDX_INPUT_LAST_TS
    if not TASKS:
        return
    TASK_IDX = int(new_idx) % len(TASKS)
    TASK_IDX_INPUT = ""
    TASK_IDX_INPUT_LAST_TS = 0.0
    task = get_selected_task()
    logger_mp.info(f"[task] selected idx={TASK_IDX} name={task.get('task_name')} prompt={task.get('task_desc')}")

def shift_task_idx(delta: int) -> None:
    global TASKS
    if not TASKS:
        return
    set_task_idx(TASK_IDX + int(delta))

def apply_task_to_recorder(recorder: EpisodeWriter, task: Dict[str, Any], task_idx: int, base_task_name: str) -> None:
    # Keep EpisodeWriter schema compatible while storing extra metadata.
    recorder.text["goal"] = task.get("task_desc", "")
    if "task_long_desc" in task:
        recorder.text["desc"] = task.get("task_long_desc", "")
    if "steps" in task:
        recorder.text["steps"] = task.get("steps", "")
    recorder.text["task_name"] = base_task_name
    # prompt/task variant selection
    recorder.text["prompt_idx"] = int(task_idx)
    recorder.text["task_idx"] = int(task_idx)
    if "item_id" in task:
        recorder.text["item_id"] = task.get("item_id")

def _handle_task_selection_key(key: str) -> bool:
    global TASK_IDX_INPUT, TASK_IDX_INPUT_LAST_TS, RECORD_RUNNING

    is_task_key = key in ("left", "right", "up", "down", "[", "]", "esc", "escape", "backspace", "enter") or (
        len(key) == 1 and key.isdigit()
    )
    if not is_task_key:
        return False
    if RECORD_RUNNING:
        # Ignore task switching while recording, but don't warn.
        return True

    if key in ("left", "up", "["):
        shift_task_idx(-1)
        return True
    if key in ("right", "down", "]"):
        shift_task_idx(1)
        return True

    if key in ("esc", "escape"):
        TASK_IDX_INPUT = ""
        TASK_IDX_INPUT_LAST_TS = 0.0
        return True
    if key in ("backspace",):
        if TASK_IDX_INPUT:
            TASK_IDX_INPUT = TASK_IDX_INPUT[:-1]
            TASK_IDX_INPUT_LAST_TS = time.time()
        return True
    if key in ("enter",):
        if TASK_IDX_INPUT:
            try:
                set_task_idx(int(TASK_IDX_INPUT))
            except Exception:
                logger_mp.warning(f"[task] invalid index input: {TASK_IDX_INPUT}")
            finally:
                TASK_IDX_INPUT = ""
                TASK_IDX_INPUT_LAST_TS = 0.0
        return True

    if len(key) == 1 and key.isdigit():
        if len(TASKS) <= 10:
            set_task_idx(int(key))
        else:
            TASK_IDX_INPUT += key
            TASK_IDX_INPUT_LAST_TS = time.time()
        return True

    return False

def cv2_keycode_to_key(key_code: int) -> Optional[str]:
    if key_code is None or key_code < 0 or key_code == 255:
        return None

    # Common special keys
    if key_code in (10, 13):
        return "enter"
    if key_code in (8,):
        return "backspace"
    if key_code in (27,):
        return "esc"

    # Arrow keys (cv2.waitKeyEx codes vary by platform/backend)
    arrow_map = {
        81: "left",
        82: "up",
        83: "right",
        84: "down",
        2424832: "left",
        2490368: "up",
        2555904: "right",
        2621440: "down",
        65361: "left",
        65362: "up",
        65363: "right",
        65364: "down",
        63234: "left",
        63232: "up",
        63235: "right",
        63233: "down",
    }
    if key_code in arrow_map:
        return arrow_map[key_code]

    # Regular ASCII keys
    if 0 <= key_code < 256:
        try:
            ch = chr(key_code)
        except Exception:
            return None
        return ch

    return None

def draw_task_overlay(img: np.ndarray) -> None:
    if not TASKS:
        return
    task = get_selected_task()
    total = len(TASKS)

    prompt = str(task.get("task_desc", ""))
    if len(prompt) > 90:
        prompt = prompt[:87] + "..."

    base_name = BASE_TASK_NAME or ""
    lines = [
        f"Task: {base_name}  Prompt [{TASK_IDX}/{total-1}]",
        prompt,
    ]
    if TASK_IDX_INPUT:
        lines.append(f"Index: {TASK_IDX_INPUT} (Enter to select)")
    else:
        lines.append("Arrows: prev/next | 0-9: select | Enter: multi-digit")

    x, y = 10, 18
    for line in lines:
        cv2.putText(img, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        y += 18

def on_press(key):
    global STOP, START, RECORD_TOGGLE
    if key == 'r':
        START = True
    elif key == 'q':
        START = False
        STOP = True
    elif key == 's' and START == True:
        RECORD_TOGGLE = True
    elif _handle_task_selection_key(key):
        pass
    else:
        logger_mp.warning(f"[on_press] {key} was pressed, but no action is defined for this key.")

def on_info(info):
    """Only handle CMD_TOGGLE_RECORD's task info"""
    global TASK_NAME, TASK_DESC, ITEM_ID
    TASK_NAME   = info.get("task_name")
    TASK_DESC   = info.get("task_desc")
    ITEM_ID     = info.get("item_id")
    logger_mp.debug(f"[on_info] Updated globals: {TASK_NAME}, {TASK_DESC}, {ITEM_ID}")

def get_state() -> dict:
    """Return current heartbeat state"""
    global START, STOP, RECORD_RUNNING, RECORD_READY
    return {
        "START": START,
        "STOP": STOP,
        "RECORD_RUNNING": RECORD_RUNNING,
        "RECORD_READY": RECORD_READY,
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--frequency', type = float, default = 25.0, help = 'save data\'s frequency')

    # basic control parameters
    parser.add_argument('--xr-mode', type=str, choices=['hand', 'controller'], default='hand', help='Select XR device tracking source')
    parser.add_argument('--arm', type=str, choices=['G1_29', 'G1_23', 'H1_2', 'H1'], default='G1_29', help='Select arm controller')
    parser.add_argument('--ee', type=str, choices=['dex1', 'dex3', 'inspire1', 'brainco', 'fake_dex'], help='Select end effector controller')
    parser.add_argument('--iface', type=str, default='enx98fc84ec937b', help='Network interface for DDS (ignored in simulation mode)')
    parser.add_argument('--port', type=int, default=8012, help='Vuer server port (default: 8012)')
    # mode flags
    parser.add_argument('--motion', action = 'store_true', help = 'Enable motion control mode')
    parser.add_argument('--headless', action='store_true', help='Enable headless mode (no display)')
    parser.add_argument('--sim', action = 'store_true', help = 'Enable isaac simulation mode')
    parser.add_argument('--affinity', action = 'store_true', help = 'Enable high priority and set CPU affinity')
    parser.add_argument('--ipc', action = 'store_true', help = 'Enable IPC server to handle input; otherwise enable sshkeyboard')
    parser.add_argument('--record', action = 'store_true', help = 'Enable data recording')
    parser.add_argument('--record-side', type=str, choices=['left', 'right', 'both'], default='both', help='Select which side(s) to record')
    parser.add_argument('--task-dir', type = str, default = '/mnt/sata1/xr_teleoperate_datasets/', help = 'path to save data')
    parser.add_argument('--task-name', type = str, default = 'pick cube', help = 'task name for recording')
    parser.add_argument('--task-desc', type = str, default = 'e.g. pick the red cube on the table.', help = 'task goal for recording')
    parser.add_argument('--tasks-file', type=str, default=None, help='Path to tasks file (JSON list / TXT one-prompt-per-line).')
    parser.add_argument('--tasks', type=str, nargs='*', default=None, help='Inline task prompts (each quoted). Overrides --task-desc.')
    parser.add_argument('--task-idx', type=int, default=0, help='Initial selected task index (0-based).')

    args = parser.parse_args()
    logger_mp.info(f"args: {args}")
    _redirect_cyclonedds_trace_log()

    try:
        def filter_states_actions_by_side(states, actions, record_side, tactiles=None, torques=None):
            if tactiles is None:
                tactiles = {}
            if torques is None:
                torques = {}
            if record_side == "both":
                return states, actions, tactiles, torques
            keep_prefix = "left" if record_side == "left" else "right"
            filtered_states = {key: value for key, value in states.items() if key.startswith(keep_prefix)}
            filtered_actions = {key: value for key, value in actions.items() if key.startswith(keep_prefix)}
            filtered_tactiles = {key: value for key, value in tactiles.items() if key.startswith(keep_prefix)}
            filtered_torques = {key: value for key, value in torques.items() if key.startswith(keep_prefix)}

            # keep non-side specific entries such as body
            for key, value in states.items():
                if not key.startswith(("left_", "right_")):
                    filtered_states[key] = value
            for key, value in actions.items():
                if not key.startswith(("left_", "right_")):
                    filtered_actions[key] = value
            for key, value in tactiles.items():
                if not key.startswith(("left_", "right_")):
                    filtered_tactiles[key] = value
            for key, value in torques.items():
                if not key.startswith(("left_", "right_")):
                    filtered_torques[key] = value
            return filtered_states, filtered_actions, filtered_tactiles, filtered_torques

        # multi-task prompts
        TASKS = load_tasks(args.tasks_file, args.tasks, args.task_name, args.task_desc)
        BASE_TASK_NAME = args.task_name
        set_task_idx(args.task_idx)
        if len(TASKS) > 1:
            logger_mp.info("Task selection: use arrow keys (←/→/↑/↓) or index (0-9 / enter for multi-digit) before starting each episode.")

        # ipc communication. client usage: see utils/ipc.py
        if args.ipc:
            ipc_server = IPC_Server(on_press=on_press, on_info=on_info, get_state=get_state)
            ipc_server.start()
        # sshkeyboard communication
        else:
            listen_keyboard_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": on_press, "until": None, "sequential": False,}, daemon=True)
            listen_keyboard_thread.start()

        # image client: img_config should be the same as the configuration in image_server.py (of Robot's development computing unit)
        if args.sim:
            img_config = {
                'fps': 30,
                'head_camera_type': 'opencv',
                'head_camera_image_shape': [480, 640],  # Head camera resolution
                'head_camera_id_numbers': ['243722071701'],
                # 'wrist_camera_type': 'opencv',
                # 'wrist_camera_image_shape': [480, 640],  # Wrist camera resolution
                # 'wrist_camera_id_numbers': [2, 4],
            }
        else:
            #HIVE-INFO: This config is for only a single camera (head)
            # img_config = {
            #    'fps': 30,
            #    'head_camera_type': 'realsense',
            #    'head_camera_image_shape': [480, 640],  # Head camera resolution
            #    'head_camera_id_numbers': ["233622072924"], #243722071701
            # }
            
            # HIVE-INFO: Use this config for extra cameras, adjust it accordingly.
            # img_config = {
            #     'fps': 30,
            #     'head_camera_type': 'realsense',
            #     'head_camera_image_shape': [480, 640],  # Head camera resolution
            #     'head_camera_id_numbers': ["233622072924"],
            #     'wrist_camera_type': 'opencv',
            #     'wrist_camera_image_shape': [480, 640],  # Wrist camera resolution
            #     'wrist_camera_id_numbers': [6],
            # }
            
            img_config = {
                'fps': 30,

                'head_camera_type': 'realsense',
                'head_camera_image_shape': [480, 640],
                'head_camera_id_numbers': ["233622072924"],

                # Mixed wrist cameras:
                # - OpenCV uses /dev/video index (int) or "/dev/videoX" (string)
                # - RealSense uses serial number (string)
                'wrist_camera_type': ['realsense', 'realsense'],
                'wrist_camera_image_shape': [480, 640],
                'wrist_camera_id_numbers': ["323622271193", "335122271374"],
            }  



        ASPECT_RATIO_THRESHOLD = 2.0 # If the aspect ratio exceeds this value, it is considered binocular
        WRIST_2CAM = False
        if len(img_config['head_camera_id_numbers']) > 1 or (img_config['head_camera_image_shape'][1] / img_config['head_camera_image_shape'][0] > ASPECT_RATIO_THRESHOLD):
            BINOCULAR = True
        else:
            BINOCULAR = False
        if 'wrist_camera_type' in img_config:
            WRIST = True
            if len(img_config['wrist_camera_id_numbers']) > 1 :
                WRIST_2CAM = True
        else:
            WRIST = False
        
        if BINOCULAR and not (img_config['head_camera_image_shape'][1] / img_config['head_camera_image_shape'][0] > ASPECT_RATIO_THRESHOLD):
            tv_img_shape = (img_config['head_camera_image_shape'][0], img_config['head_camera_image_shape'][1] * 2, 3)
        else:
            tv_img_shape = (img_config['head_camera_image_shape'][0], img_config['head_camera_image_shape'][1], 3)

        tv_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(tv_img_shape) * np.uint8().itemsize)
        tv_img_array = np.ndarray(tv_img_shape, dtype = np.uint8, buffer = tv_img_shm.buf)

        if WRIST and args.sim:
            wrist_img_shape = (img_config['wrist_camera_image_shape'][0], img_config['wrist_camera_image_shape'][1] * 2, 3)
            wrist_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(wrist_img_shape) * np.uint8().itemsize)
            wrist_img_array = np.ndarray(wrist_img_shape, dtype = np.uint8, buffer = wrist_img_shm.buf)
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name, 
                                    wrist_img_shape = wrist_img_shape, wrist_img_shm_name = wrist_img_shm.name, server_address="127.0.0.1")
        elif WRIST and WRIST_2CAM and not args.sim:
            print("----- dual wrist camera mode")
            wrist_img_shape = (img_config['wrist_camera_image_shape'][0], img_config['wrist_camera_image_shape'][1] * 2, 3)
            wrist_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(wrist_img_shape) * np.uint8().itemsize)
            wrist_img_array = np.ndarray(wrist_img_shape, dtype = np.uint8, buffer = wrist_img_shm.buf)
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name, 
                                    wrist_img_shape = wrist_img_shape, wrist_img_shm_name = wrist_img_shm.name)
        elif WRIST and not WRIST_2CAM and not args.sim:
            print("----- single wrist camera mode")
            wrist_img_shape = (img_config['wrist_camera_image_shape'][0], img_config['wrist_camera_image_shape'][1], 3)
            wrist_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(wrist_img_shape) * np.uint8().itemsize)
            wrist_img_array = np.ndarray(wrist_img_shape, dtype = np.uint8, buffer = wrist_img_shm.buf)
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name, 
                                    wrist_img_shape = wrist_img_shape, wrist_img_shm_name = wrist_img_shm.name)
        else:
            print("----- no wrist camera mode")
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name)

        image_receive_thread = threading.Thread(target = img_client.receive_process, daemon = True)
        image_receive_thread.daemon = True
        image_receive_thread.start()

        # television: obtain hand pose data from the XR device and transmit the robot's head camera image to the XR device.
        tv_wrapper = TeleVuerWrapper(binocular=BINOCULAR, use_hand_tracking=args.xr_mode == "hand", img_shape=tv_img_shape, img_shm_name=tv_img_shm.name, 
                                     return_state_data=True, return_hand_rot_data = False, port=args.port)
        
        

        # arm
        if args.arm == "G1_29":
            arm_ik = G1_29_ArmIK()
            arm_ctrl = G1_29_ArmController(motion_mode=args.motion, simulation_mode=args.sim, dds_interface=args.iface)
            from teleop.robot_control.robot_arm import G1_29_JointIndex
            WAIST_INDICES = [G1_29_JointIndex.kWaistYaw]  # Only record yaw (what we actually control)
        elif args.arm == "G1_23":
            arm_ik = G1_23_ArmIK()
            arm_ctrl = G1_23_ArmController(motion_mode=args.motion, simulation_mode=args.sim, dds_interface=args.iface)
        elif args.arm == "H1_2":
            arm_ik = H1_2_ArmIK()
            arm_ctrl = H1_2_ArmController(motion_mode=args.motion, simulation_mode=args.sim, dds_interface=args.iface)
        elif args.arm == "H1":
            arm_ik = H1_ArmIK()
            arm_ctrl = H1_ArmController(simulation_mode=args.sim, dds_interface=args.iface)

        # end-effector
        if args.ee == "dex3":
            left_hand_pos_array = Array('d', 75, lock = True)      # [input]
            right_hand_pos_array = Array('d', 75, lock = True)     # [input]
            dual_hand_data_lock = Lock()
            dual_hand_state_array = Array('d', 14, lock = False)   # [output] current left, right hand state(14) data.
            dual_hand_action_array = Array('d', 14, lock = False)  # [output] current left, right hand action(14) data.
            right_hand_override = Array('d', 1, lock = True)
            right_hand_override[0] = 1.0  # Start with full control
            left_hand_override = Array('d', 1, lock = True)
            left_hand_override[0] = 1.0  # Start with full control
            hand_ctrl = Dex3_1_Controller(left_hand_pos_array, right_hand_pos_array,
                                          dual_hand_data_lock, dual_hand_state_array, dual_hand_action_array, 
                                          simulation_mode=args.sim, right_hand_override=right_hand_override, left_hand_override=left_hand_override,
                                          dds_interface=args.iface)
            
            dex3_right_pub = ChannelPublisher("rt/dex3/right/cmd", HandCmd_)
            dex3_right_pub.Init()
            dex3_right_msg = unitree_hg_msg_dds__HandCmd_()
            
            for jid in Dex3_1_Right_JointIndex:
                ris = hand_ctrl._RIS_Mode(id=jid, status=0x01)
                dex3_right_msg.motor_cmd[jid].mode = ris._mode_to_uint8()
                dex3_right_msg.motor_cmd[jid].kp = 1.5
                dex3_right_msg.motor_cmd[jid].kd = 0.2

            dex3_left_pub = ChannelPublisher("rt/dex3/left/cmd", HandCmd_)
            dex3_left_pub.Init()
            dex3_left_msg = unitree_hg_msg_dds__HandCmd_()
            
            for jid in Dex3_1_Left_JointIndex:
                ris = hand_ctrl._RIS_Mode(id=jid, status=0x01)
                dex3_left_msg.motor_cmd[jid].mode = ris._mode_to_uint8()
                dex3_left_msg.motor_cmd[jid].kp = 1.5
                dex3_left_msg.motor_cmd[jid].kd = 0.2

            # --- Dex3 state subscribers (for torque + pressure contact detection) ---
            dex3_right_state_sub = ChannelSubscriber("rt/dex3/right/state", HandState_)
            dex3_right_state_sub.Init()

            dex3_left_state_sub = ChannelSubscriber("rt/dex3/left/state", HandState_)
            dex3_left_state_sub.Init()

            # --- contact detection state ---
            right_tau = np.zeros(7, dtype=np.float64)
            left_tau  = np.zeros(7, dtype=np.float64)

            # Dex3 has 9 pressure sensors in your other controller; keep same size for now
            right_press = np.zeros(9, dtype=np.float64)
            left_press  = np.zeros(9, dtype=np.float64)

            # baseline for pressure (optional but recommended)
            right_press_base = np.zeros(9, dtype=np.float64)
            left_press_base  = np.zeros(9, dtype=np.float64)
            press_base_ready = False
            press_base_samples = 0
            PRESS_BASE_N = 5

            # PER-MOTOR hold tracking (like hand_controller.py)
            right_hold_logged = [False] * 7
            left_hold_logged = [False] * 7
            right_ramped_target = np.zeros(7, dtype=np.float64)
            left_ramped_target = np.zeros(7, dtype=np.float64)


        elif args.ee == "fake_dex":
            left_hand_pos_array = Array('d', 75, lock = True)      # [input]
            right_hand_pos_array = Array('d', 75, lock = True)     # [input]
            dual_hand_data_lock = Lock()
            dual_hand_state_array = Array('d', 14, lock = False)   # [output] current left, right hand state(14) data.
            dual_hand_action_array = Array('d', 14, lock = False)  # [output] current left, right hand action(14) data.
            hand_ctrl = None

            dex3_left_pub = ChannelPublisher("rt/dex3/left/cmd", HandCmd_)
            dex3_left_pub.Init()
            dex3_left_msg = unitree_hg_msg_dds__HandCmd_()

            # 简单版：直接给 mode/kp/kd 默认值（或者用上面“从 state 抄”的版）
            for jid in Dex3_1_Left_JointIndex:
                dex3_left_msg.motor_cmd[jid].mode = 10
                dex3_left_msg.motor_cmd[jid].kp   = 1.5
                dex3_left_msg.motor_cmd[jid].kd   = 0.2
                dex3_left_msg.motor_cmd[jid].tau  = 0.0
                dex3_left_msg.motor_cmd[jid].dq   = 0.0
                
        else:
            pass
        
        # affinity mode (if you dont know what it is, then you probably don't need it)
        if args.affinity:
            import psutil
            p = psutil.Process(os.getpid())
            p.cpu_affinity([0,1,2,3]) # Set CPU affinity to cores 0-3
            try:
                p.nice(-20) # Set highest priority
                # logger_mp.info("Set high priority successfully.")
            except psutil.AccessDenied:
                logger_mp.warning("Failed to set high priority. Please run as root.")
                
            for child in p.children(recursive=True):
                try:
                    # logger_mp.info(f"Child process {child.pid} name: {child.name()}")
                    child.cpu_affinity([5,6])
                    child.nice(-20)
                except psutil.AccessDenied:
                    pass

        # simulation mode
        if args.sim:
            reset_pose_publisher = ChannelPublisher("rt/reset_pose/cmd", String_)
            reset_pose_publisher.Init()
            from teleop.utils.sim_state_topic import start_sim_state_subscribe
            sim_state_subscriber = start_sim_state_subscribe()

        # controller + motion mode
        if args.xr_mode == "controller" and args.motion:
            from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
            sport_client = LocoClient()
            sport_client.SetTimeout(0.0001)
            sport_client.Init()

        # record + headless mode
        if args.record:
            record_task_dir = os.path.join(args.task_dir, args.task_name)
            initial_task = get_selected_task()
            recorder = EpisodeWriter(
                task_dir=record_task_dir,
                task_goal=initial_task.get("task_desc", args.task_desc),
                frequency=args.frequency,
                rerun_log=not args.headless,
            )
            if args.xr_mode == "controller":
                recorder.info["joint_names"]["left_trig"] = ["left_trig"]
                recorder.info["joint_names"]["right_trig"] = ["right_trig"]
            apply_task_to_recorder(recorder, initial_task, TASK_IDX, args.task_name)
            logger_mp.info(f"Recording side: {args.record_side}")


        logger_mp.info("Please enter the start signal (enter 'r' to start the subsequent program)")
        while not START and not STOP:
            time.sleep(0.01)
        logger_mp.info("start program.")
        arm_ctrl.speed_gradual_max()

        grab_pose_right = np.array([-0.0,-1.0,-1.70,1.55,1.75,1.55,1.75])  # Palmar grip
        grab_pose_left = np.array([0.0,1.0,1.70,-1.55,-1.75,-1.55,-1.75])  # Palmar grip
        open_pose = np.array([0,0,0,0,0,0,0])
        scoop_pose_left = np.array([0.00, -0.70, 1.70, 0.00, -1.75, 0.00, -1.75], dtype=float)
        scoop_pose_right = np.array([0.00, 0.70, -1.70, 0.00, 1.75, 0.00, 1.75], dtype=float)

        # --- SmartGrip parameters ---
        KP_MOVE = 1.5
        KD_MOVE = 0.2
        KP_HOLD = 0.8      # soft hold like hand_controller.py
        KD_HOLD = 0.2

        # Hysteresis thresholds (matching hand_controller.py)
        PRESSURE_THRESHOLD = 0.04              # Higher - to ENTER hold
        PRESSURE_THRESHOLD_BASE = 0.04         # Base sensor threshold (enter)
        PRESSURE_THRESHOLD_EXIT = 0.03         # Lower - to EXIT hold (sticky)
        PRESSURE_THRESHOLD_BASE_EXIT = 0.03    # Base sensor threshold (exit)
        TORQUE_THRESHOLD_HIGH = 200000.0
        
        SQUEEZE_OFFSET = 0.05     # matching hand_controller.py
        RAMP_FACTOR = 0.30        # smooth ramping
        THUMB_COMPLETION_THRESHOLD = 0.05
        
        # --- Tare (recalibration) tracking ---
        # Arm tare on trigger press, but execute only when hand reaches fully-open pose.
        TARE_OPEN_TOL = 0.05
        right_tare_pending = False
        left_tare_pending = False
        right_trigger_prev = False
        left_trigger_prev = False
        
        # Initialize ramped targets to grab pose (closed hands) since we start closed
        if args.ee == "dex3":
            right_ramped_target[:] = grab_pose_right
            left_ramped_target[:] = grab_pose_left
        
        # Navigation velocity tracking (for recording)
        nav_vx = 0.0
        nav_vy = 0.0
        nav_vyaw = 0.0
        
        loop_idx = 0
        while not STOP:
            start_time = time.time()

            if not args.headless:
                tv_resized_image = cv2.resize(tv_img_array, (tv_img_shape[1] // 2, tv_img_shape[0] // 2))
                draw_task_overlay(tv_resized_image)
                cv2.imshow("record image", tv_resized_image)
                # opencv GUI communication
                wait_fn = getattr(cv2, "waitKeyEx", cv2.waitKey)
                key_code = wait_fn(1)
                key = cv2_keycode_to_key(key_code)
                if key:
                    if key == 'a':
                        if args.sim:
                            publish_reset_category(2, reset_pose_publisher)
                    else:
                        on_press(key)
                        if key == 'q' and args.sim:
                            publish_reset_category(2, reset_pose_publisher)

            if args.record and RECORD_TOGGLE:
                RECORD_TOGGLE = False
                if not RECORD_RUNNING:
                    # Apply the currently selected task prompt to the next episode.
                    task = get_selected_task()
                    task_idx = TASK_IDX
                    if TASK_DESC is not None:
                        task = {
                            "task_name": TASK_NAME or task.get("task_name", f"task_{task_idx}"),
                            "task_desc": TASK_DESC,
                        }
                    if ITEM_ID is not None:
                        task["item_id"] = ITEM_ID
                    apply_task_to_recorder(recorder, task, task_idx, args.task_name)
                    if recorder.create_episode():
                        RECORD_RUNNING = True
                        if TASK_DESC is not None:
                            TASK_NAME, TASK_DESC, ITEM_ID = None, None, None
                    else:
                        logger_mp.error("Failed to create episode. Recording not started.")
                else:
                    RECORD_RUNNING = False
                    recorder.save_episode()
                    if args.sim:
                        publish_reset_category(1, reset_pose_publisher)

            # get input data
            tele_data = tv_wrapper.get_motion_state_data()

            if (args.ee == "dex3" or args.ee == "inspire1" or args.ee == "brainco") and args.xr_mode == "hand":
                with left_hand_pos_array.get_lock():
                    left_hand_pos_array[:] = tele_data.left_hand_pos.flatten()
                with right_hand_pos_array.get_lock():
                    right_hand_pos_array[:] = tele_data.right_hand_pos.flatten()
            else:
                pass        
            
            # high level control
            if args.xr_mode == "controller" and args.motion:
                # quit teleoperate
                if tele_data.tele_state.right_aButton:
                    START = False
                    STOP = True
                # command robot to enter damping mode. soft emergency stop function
                if tele_data.tele_state.left_thumbstick_state and tele_data.tele_state.right_thumbstick_state:
                    sport_client.Damp()
                    nav_vx, nav_vy, nav_vyaw = 0.0, 0.0, 0.0
                else:
                    # control, limit velocity to within 0.3
                    nav_vx = -tele_data.tele_state.left_thumbstick_value[1]  * 0.3
                    nav_vy = -tele_data.tele_state.left_thumbstick_value[0]  * 0.3
                    nav_vyaw = -tele_data.tele_state.right_thumbstick_value[0] * 0.3
                    sport_client.Move(nav_vx, nav_vy, nav_vyaw)
            else:
                # No motion control - velocities are zero
                nav_vx, nav_vy, nav_vyaw = 0.0, 0.0, 0.0

            # waist yaw control with A and B buttons (for controller mode)
            if args.xr_mode == "controller":
                waist_rotation_speed = 0.01  # radians per frame (adjust for slower/faster rotation)
                if tele_data.tele_state.left_aButton:
                    # A button (left controller): rotate waist yaw to the right
                    arm_ctrl.ctrl_waist_yaw(waist_rotation_speed)
                    logger_mp.debug(f"Waist yaw right: {arm_ctrl.get_waist_yaw_target():.3f}")
                elif tele_data.tele_state.left_bButton:
                    # B button (left controller): rotate waist yaw to the left
                    arm_ctrl.ctrl_waist_yaw(-waist_rotation_speed)
                    logger_mp.debug(f"Waist yaw left: {arm_ctrl.get_waist_yaw_target():.3f}")
                elif tele_data.tele_state.left_squeeze_ctrl_state:
                    # Grip button (left controller): gradually reset waist yaw to zero
                    arm_ctrl.reset_waist_yaw()
                    logger_mp.debug(f"Waist yaw resetting to zero: {arm_ctrl.get_waist_yaw_target():.3f}")

            # get current robot state data.
            current_lr_arm_q  = arm_ctrl.get_current_dual_arm_q()
            current_lr_arm_dq = arm_ctrl.get_current_dual_arm_dq()
            current_full_motor_q = arm_ctrl.get_current_motor_q()  # For waist data

            # solve ik using motor data and wrist pose, then use ik results to control arms.
            time_ik_start = time.time()
            sol_q, sol_tauff  = arm_ik.solve_ik(tele_data.left_arm_pose, tele_data.right_arm_pose, current_lr_arm_q, current_lr_arm_dq)
            time_ik_end = time.time()
            logger_mp.debug(f"ik:\t{round(time_ik_end - time_ik_start, 6)}")
            arm_ctrl.ctrl_dual_arm(sol_q, sol_tauff)

            right_trigger = tele_data.tele_state.right_trigger_state
            left_trigger = tele_data.tele_state.left_trigger_state
            
            # --- Detect trigger press and arm tare ---
            
            # Right hand: detect rising edge (was not pressed, now pressed)
            if not right_trigger_prev and right_trigger:
                right_tare_pending = True
                logger_mp.info("[TARE] Right trigger pressed, waiting for fully-open hand to tare...")
            right_trigger_prev = right_trigger
            
            # Left hand: detect rising edge (was not pressed, now pressed)
            if not left_trigger_prev and left_trigger:
                left_tare_pending = True
                logger_mp.info("[TARE] Left trigger pressed, waiting for fully-open hand to tare...")
            left_trigger_prev = left_trigger

            # --- Read Dex3 state (tau_est + pressure) ---
            if args.ee == "dex3":
                try:
                    rmsg = dex3_right_state_sub.Read()
                    lmsg = dex3_left_state_sub.Read()

                    # torques: map by joint indices, keep 7-length order consistent with your cmd loops
                    if rmsg is not None:
                        for i, jid in enumerate(Dex3_1_Right_JointIndex):
                            right_tau[i] = float(rmsg.motor_state[jid].tau_est)

                        # pressure: average pads per sensor (same idea as hand_controller.py)
                        m = min(9, len(rmsg.press_sensor_state))
                        for si in range(m):
                            pads = rmsg.press_sensor_state[si].pressure
                            if len(pads) > 0:
                                right_press[si] = float(sum(pads) / len(pads))
                            else:
                                right_press[si] = 0.0

                    if lmsg is not None:
                        for i, jid in enumerate(Dex3_1_Left_JointIndex):
                            left_tau[i] = float(lmsg.motor_state[jid].tau_est)

                        m = min(9, len(lmsg.press_sensor_state))
                        for si in range(m):
                            pads = lmsg.press_sensor_state[si].pressure
                            if len(pads) > 0:
                                left_press[si] = float(sum(pads) / len(pads))
                            else:
                                left_press[si] = 0.0

                    # baseline calibration (only once, early)
                    if not press_base_ready:
                        right_press_base += right_press
                        left_press_base  += left_press
                        press_base_samples += 1
                        if press_base_samples >= PRESS_BASE_N:
                            right_press_base /= press_base_samples
                            left_press_base  /= press_base_samples
                            press_base_ready = True

                except Exception:
                    # if state not available (sim / DDS hiccup), just keep last values
                    pass
                
                # --- Execute tare only when trigger is held and hand is fully open ---
                right_is_fully_open = np.max(np.abs(right_ramped_target - open_pose)) <= TARE_OPEN_TOL
                left_is_fully_open = np.max(np.abs(left_ramped_target - open_pose)) <= TARE_OPEN_TOL

                if right_tare_pending and right_trigger and right_is_fully_open:
                    right_press_base = right_press.copy()
                    right_tare_pending = False
                    logger_mp.debug("[TARE] Right hand recalibrated at fully-open pose.")

                if left_tare_pending and left_trigger and left_is_fully_open:
                    left_press_base = left_press.copy()
                    left_tare_pending = False
                    logger_mp.debug("[TARE] Left hand recalibrated at fully-open pose.")

                # baseline-correct and normalize (divide by 100.0 like hand_controller.py)
                PRESSURE_SCALE = 100.0
                if press_base_ready:
                    right_press_corr = np.maximum(0.0, (right_press - right_press_base) / PRESSURE_SCALE)
                    left_press_corr  = np.maximum(0.0, (left_press  - left_press_base)  / PRESSURE_SCALE)
                else:
                    right_press_corr = right_press / PRESSURE_SCALE
                    left_press_corr  = left_press / PRESSURE_SCALE

                loop_idx += 1

            if args.ee == "fake_dex":
                fake_q14 = np.zeros(14,dtype=np.float64)

                if left_trigger:
                    fake_q14[:7] = open_pose
                else:
                    fake_q14[:7] = grab_pose_left

                if right_trigger:
                    fake_q14[-7:] = open_pose
                else:
                    fake_q14[-7:] = grab_pose_right

                with dual_hand_data_lock:
                    dual_hand_action_array[:] = fake_q14
                    dual_hand_state_array[:] = fake_q14

                left7 = fake_q14[:7]
                for i, jid in enumerate(Dex3_1_Left_JointIndex):
                    dex3_left_msg.motor_cmd[jid].q = left7[i]
                dex3_left_pub.Write(dex3_left_msg)
                
            elif args.ee == "dex3":
                q14 = np.array(dual_hand_action_array[:], dtype=np.float64)

                # Get corrected pressures (or fallback to raw)
                right_press_corr = right_press_corr if 'right_press_corr' in locals() else right_press
                left_press_corr = left_press_corr if 'left_press_corr' in locals() else left_press
                
                # Extract finger pressures (matching hand_controller.py getFingerPressures)
                # Right hand
                right_thumb_tip = right_press_corr[1]
                right_thumb_base = right_press_corr[0]
                right_index_tip = right_press_corr[3]
                right_index_base = right_press_corr[2]
                right_middle_tip = right_press_corr[5]
                right_middle_base = right_press_corr[4]
                
                # Left hand
                left_thumb_tip = left_press_corr[1]
                left_thumb_base = left_press_corr[0]
                left_index_tip = left_press_corr[5]
                left_index_base = left_press_corr[4]
                left_middle_tip = left_press_corr[3]
                left_middle_base = left_press_corr[2]

                # --- DEBUG: print finger-specific pressures and torques ---
                # if press_base_ready and loop_idx % 1 == 0:  # Print every loop
                #     logger_mp.info(
                #         f"[HAND DEBUG] RIGHT: thumb_b={right_thumb_base:.3f} thumb_t={right_thumb_tip:.3f} "
                #         f"idx_b={right_index_base:.3f} idx_t={right_index_tip:.3f} mid_b={right_middle_base:.3f} mid_t={right_middle_tip:.3f} | "
                #         f"tau_max={float(np.max(np.abs(right_tau))):.0f}"
                #     )
                #     logger_mp.info(
                #         f"[HAND DEBUG] LEFT: thumb_b={left_thumb_base:.3f} thumb_t={left_thumb_tip:.3f} "
                #         f"idx_b={left_index_base:.3f} idx_t={left_index_tip:.3f} mid_b={left_middle_base:.3f} mid_t={left_middle_tip:.3f} | "
                #         f"tau_max={float(np.max(np.abs(left_tau))):.0f}"
                #     )

                # ---------------- RIGHT hand (per-motor SmartGrip) ----------------
                if not right_trigger:
                    # take ownership while gripping
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 1.0

                    # User is gripping - use grab target with SmartGrip
                    target_pose = grab_pose_right
                    with dual_hand_data_lock:
                        current_pos = np.array(dual_hand_state_array[-7:], dtype=np.float64)
                    
                    # Update thumb target with ramping (thumb moves first)
                    final_thumb_target = target_pose[0]
                    new_thumb_ramped = right_ramped_target[0] + (final_thumb_target - right_ramped_target[0]) * RAMP_FACTOR
                    right_ramped_target[0] = new_thumb_ramped
                    thumb_is_done = abs(new_thumb_ramped - final_thumb_target) < THUMB_COMPLETION_THRESHOLD
                    
                    # Process each motor individually
                    for i, jid in enumerate(Dex3_1_Right_JointIndex):
                        final_target = target_pose[i]
                        
                        # Determine thresholds based on current hold state (hysteresis)
                        if right_hold_logged[i]:
                            thresh_main = PRESSURE_THRESHOLD_EXIT       # Lower to exit
                            thresh_base = PRESSURE_THRESHOLD_BASE_EXIT
                        else:
                            thresh_main = PRESSURE_THRESHOLD            # Higher to enter
                            thresh_base = PRESSURE_THRESHOLD_BASE
                        
                        is_high_torque = abs(right_tau[i]) > TORQUE_THRESHOLD_HIGH
                        should_hold = False
                        
                        # Per-motor pressure check (matching hand_controller.py logic)
                        hold_reasons = []
                        if i == 1:  # Thumb base
                            if right_thumb_base > thresh_main:
                                hold_reasons.append(f"thumb_base_press={right_thumb_base:.3f}>{thresh_main:.3f}")
                            if right_thumb_tip > thresh_main:
                                hold_reasons.append(f"thumb_tip_press={right_thumb_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 2:  # Thumb tip
                            if right_thumb_tip > thresh_main:
                                hold_reasons.append(f"thumb_tip_press={right_thumb_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 3:  # Middle base (safety link)
                            if right_middle_base > thresh_base:
                                hold_reasons.append(f"middle_base_press={right_middle_base:.3f}>{thresh_base:.3f}")
                            if right_middle_tip > thresh_main:
                                hold_reasons.append(f"middle_tip_press={right_middle_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 4:  # Middle tip
                            if right_middle_tip > thresh_main:
                                hold_reasons.append(f"middle_tip_press={right_middle_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 5:  # Index base (safety link)
                            if right_index_base > thresh_base:
                                hold_reasons.append(f"index_base_press={right_index_base:.3f}>{thresh_base:.3f}")
                            if right_index_tip > thresh_main:
                                hold_reasons.append(f"index_tip_press={right_index_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 6:  # Index tip
                            if right_index_tip > thresh_main:
                                hold_reasons.append(f"index_tip_press={right_index_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(right_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        
                        if should_hold:
                            # Enter or maintain hold
                            if not right_hold_logged[i]:
                                # First contact - snap to smart target
                                direction = 1.0 if target_pose[i] > current_pos[i] else -1.0
                                smart_target = current_pos[i] + (SQUEEZE_OFFSET * direction)
                                right_ramped_target[i] = smart_target
                                finger_names = ["thumb_rot", "thumb_base", "thumb_tip", "middle_base", "middle_tip", "index_base", "index_tip"]
                                #logger_mp.info(f"[RIGHT {finger_names[i]}] HOLDING due to: {', '.join(hold_reasons)}")
                                right_hold_logged[i] = True
                            
                            # Hold with soft gains
                            dex3_right_msg.motor_cmd[jid].q = right_ramped_target[i]
                            dex3_right_msg.motor_cmd[jid].kp = KP_HOLD
                            dex3_right_msg.motor_cmd[jid].kd = KD_HOLD
                        else:
                            # Continue moving (only if thumb is done or this is thumb)
                            if i == 0 or thumb_is_done:
                                new_ramped = right_ramped_target[i] + (final_target - right_ramped_target[i]) * RAMP_FACTOR
                                right_ramped_target[i] = new_ramped
                            
                            dex3_right_msg.motor_cmd[jid].q = right_ramped_target[i]
                            dex3_right_msg.motor_cmd[jid].kp = KP_MOVE
                            dex3_right_msg.motor_cmd[jid].kd = KD_MOVE
                            right_hold_logged[i] = False
                    
                    # Update q14 for recording
                    q14[-7:] = right_ramped_target
                    
                else:
                    # Trigger pressed - open hand with ramping
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 1.0

                    for i, jid in enumerate(Dex3_1_Right_JointIndex):
                        # Open smoothly with ramping
                        final_target = open_pose[i]
                        new_ramped = right_ramped_target[i] + (final_target - right_ramped_target[i]) * RAMP_FACTOR
                        right_ramped_target[i] = new_ramped
                        
                        dex3_right_msg.motor_cmd[jid].q = right_ramped_target[i]
                        dex3_right_msg.motor_cmd[jid].kp = KP_MOVE
                        dex3_right_msg.motor_cmd[jid].kd = KD_MOVE
                        right_hold_logged[i] = False
                    
                    q14[-7:] = right_ramped_target

                # ---------------- LEFT hand (per-motor SmartGrip) ----------------
                if not left_trigger:
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 1.0

                    # User is gripping - use grab target with SmartGrip
                    target_pose = grab_pose_left
                    with dual_hand_data_lock:
                        current_pos = np.array(dual_hand_state_array[:7], dtype=np.float64)
                    
                    # Update thumb target with ramping (thumb moves first)
                    final_thumb_target = target_pose[0]
                    new_thumb_ramped = left_ramped_target[0] + (final_thumb_target - left_ramped_target[0]) * RAMP_FACTOR
                    left_ramped_target[0] = new_thumb_ramped
                    thumb_is_done = abs(new_thumb_ramped - final_thumb_target) < THUMB_COMPLETION_THRESHOLD
                    
                    # Process each motor individually
                    for i, jid in enumerate(Dex3_1_Left_JointIndex):
                        final_target = target_pose[i]
                        
                        # Determine thresholds based on current hold state (hysteresis)
                        if left_hold_logged[i]:
                            thresh_main = PRESSURE_THRESHOLD_EXIT       # Lower to exit
                            thresh_base = PRESSURE_THRESHOLD_BASE_EXIT
                        else:
                            thresh_main = PRESSURE_THRESHOLD            # Higher to enter
                            thresh_base = PRESSURE_THRESHOLD_BASE
                        
                        is_high_torque = abs(left_tau[i]) > TORQUE_THRESHOLD_HIGH
                        should_hold = False
                        
                        # Per-motor pressure check (matching hand_controller.py logic for LEFT)
                        hold_reasons = []
                        if i == 1:  # Thumb base
                            if left_thumb_base > thresh_main:
                                hold_reasons.append(f"thumb_base_press={left_thumb_base:.3f}>{thresh_main:.3f}")
                            if left_thumb_tip > thresh_main:
                                hold_reasons.append(f"thumb_tip_press={left_thumb_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 2:  # Thumb tip
                            if left_thumb_tip > thresh_main:
                                hold_reasons.append(f"thumb_tip_press={left_thumb_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 3:  # Middle base (safety link)
                            if left_middle_base > thresh_base:
                                hold_reasons.append(f"middle_base_press={left_middle_base:.3f}>{thresh_base:.3f}")
                            if left_middle_tip > thresh_main:
                                hold_reasons.append(f"middle_tip_press={left_middle_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 4:  # Middle tip
                            if left_middle_tip > thresh_main:
                                hold_reasons.append(f"middle_tip_press={left_middle_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 5:  # Index base (safety link)
                            if left_index_base > thresh_base:
                                hold_reasons.append(f"index_base_press={left_index_base:.3f}>{thresh_base:.3f}")
                            if left_index_tip > thresh_main:
                                hold_reasons.append(f"index_tip_press={left_index_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        elif i == 6:  # Index tip
                            if left_index_tip > thresh_main:
                                hold_reasons.append(f"index_tip_press={left_index_tip:.3f}>{thresh_main:.3f}")
                            if is_high_torque:
                                hold_reasons.append(f"torque={abs(left_tau[i]):.1f}>{TORQUE_THRESHOLD_HIGH:.1f}")
                            should_hold = len(hold_reasons) > 0
                        
                        if should_hold:
                            # Enter or maintain hold
                            if not left_hold_logged[i]:
                                # First contact - snap to smart target
                                direction = 1.0 if target_pose[i] > current_pos[i] else -1.0
                                smart_target = current_pos[i] + (SQUEEZE_OFFSET * direction)
                                left_ramped_target[i] = smart_target
                                finger_names = ["thumb_rot", "thumb_base", "thumb_tip", "middle_base", "middle_tip", "index_base", "index_tip"]
                                #logger_mp.info(f"[LEFT {finger_names[i]}] HOLDING due to: {', '.join(hold_reasons)}")
                                left_hold_logged[i] = True
                            
                            # Hold with soft gains
                            dex3_left_msg.motor_cmd[jid].q = left_ramped_target[i]
                            dex3_left_msg.motor_cmd[jid].kp = KP_HOLD
                            dex3_left_msg.motor_cmd[jid].kd = KD_HOLD
                        else:
                            # Continue moving (only if thumb is done or this is thumb)
                            if i == 0 or thumb_is_done:
                                new_ramped = left_ramped_target[i] + (final_target - left_ramped_target[i]) * RAMP_FACTOR
                                left_ramped_target[i] = new_ramped
                            
                            dex3_left_msg.motor_cmd[jid].q = left_ramped_target[i]
                            dex3_left_msg.motor_cmd[jid].kp = KP_MOVE
                            dex3_left_msg.motor_cmd[jid].kd = KD_MOVE
                            left_hold_logged[i] = False
                    
                    # Update q14 for recording
                    q14[:7] = left_ramped_target                    

                else:
                    # Trigger pressed - open hand with ramping
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 1.0

                    for i, jid in enumerate(Dex3_1_Left_JointIndex):
                        # Open smoothly with ramping
                        final_target = open_pose[i]
                        new_ramped = left_ramped_target[i] + (final_target - left_ramped_target[i]) * RAMP_FACTOR
                        left_ramped_target[i] = new_ramped
                        
                        dex3_left_msg.motor_cmd[jid].q = left_ramped_target[i]
                        dex3_left_msg.motor_cmd[jid].kp = KP_MOVE
                        dex3_left_msg.motor_cmd[jid].kd = KD_MOVE
                        left_hold_logged[i] = False
                    
                    q14[:7] = left_ramped_target

                # Publish the commands (q values already set in per-motor loops above)
                dex3_right_pub.Write(dex3_right_msg)
                dex3_left_pub.Write(dex3_left_msg)

                # keep recorded actions in sync with the commands we just sent
                with dual_hand_data_lock:
                    dual_hand_action_array[:] = q14
            else:
                pass
            

            # record data
            if args.record:
                RECORD_READY = recorder.is_ready()
                with dual_hand_data_lock:
                    left_ee_state = dual_hand_state_array[:7]
                    right_ee_state = dual_hand_state_array[-7:]
                    left_hand_action = dual_hand_action_array[:7]
                    right_hand_action = dual_hand_action_array[-7:]
                if args.xr_mode == "controller":
                    left_trigger_action = int(bool(left_trigger))
                    right_trigger_action = int(bool(right_trigger))

                # waist state and action (only yaw - what we actually control)
                if WAIST_INDICES:
                    current_waist_state = [float(current_full_motor_q[WAIST_INDICES[0]])]
                    waist_yaw_target = arm_ctrl.get_waist_yaw_target()
                    if waist_yaw_target is not None:
                        current_waist_action = [waist_yaw_target]
                    else:
                        current_waist_action = current_waist_state.copy()
                else:
                    current_waist_state = []
                    current_waist_action = []
        
                # head image
                current_tv_image = tv_img_array.copy()
                # wrist image
                if WRIST:
                    current_wrist_image = wrist_img_array.copy()
                # arm state and action
                left_arm_state  = current_lr_arm_q[:7]
                right_arm_state = current_lr_arm_q[-7:]
                left_arm_action = sol_q[:7]
                right_arm_action = sol_q[-7:]
                if RECORD_RUNNING:
                    colors = {}
                    depths = {}
                    if BINOCULAR:
                        colors[f"color_{0}"] = current_tv_image[:, :tv_img_shape[1]//2]
                        colors[f"color_{1}"] = current_tv_image[:, tv_img_shape[1]//2:]
                        if WRIST:
                            if WRIST_2CAM:
                                colors[f"color_{2}"] = current_wrist_image[:, :wrist_img_shape[1]//2]
                                colors[f"color_{3}"] = current_wrist_image[:, wrist_img_shape[1]//2:]
                            else:
                                colors[f"color_{2}"] = current_wrist_image
                            
                    else:
                        colors[f"color_{0}"] = current_tv_image
                        if WRIST:
                            if WRIST_2CAM:
                                colors[f"color_{1}"] = current_wrist_image[:, :wrist_img_shape[1]//2]
                                colors[f"color_{2}"] = current_wrist_image[:, wrist_img_shape[1]//2:]
                            else:
                                colors[f"color_{1}"] = current_wrist_image
                    states = {
                        "left_arm": {                                                                    
                            "qpos":   left_arm_state.tolist(),    # numpy.array -> list
                            "qvel":   [],                          
                            "torque": [],                        
                        }, 
                        "right_arm": {                                                                    
                            "qpos":   right_arm_state.tolist(),       
                            "qvel":   [],                          
                            "torque": [],                         
                        },                        
                        "left_ee": {                                                                    
                            "qpos":   left_ee_state,           
                            "qvel":   [],                           
                            "torque": [],                          
                        }, 
                        "right_ee": {                                                                    
                            "qpos":   right_ee_state,       
                            "qvel":   [],                           
                            "torque": [],  
                        }, 
                        "waist": {
                            "qpos": current_waist_state,
                            "qvel": [], 
                        },
                        "base": {
                            "qpos": [],  
                            "qvel": [], 
                        }, 
                    }
                    actions = {
                        "left_arm": {                                   
                            "qpos":   left_arm_action.tolist(),       
                            "qvel":   [],       
                            "torque": [],      
                        }, 
                        "right_arm": {                                   
                            "qpos":   right_arm_action.tolist(),       
                            "qvel":   [],       
                            "torque": [],       
                        },                         
                        "left_ee": {                                   
                            "qpos":   left_hand_action,       
                            "qvel":   [],       
                            "torque": [],       
                        }, 
                        "right_ee": {                                   
                            "qpos":   right_hand_action,       
                            "qvel":   [],       
                            "torque": [], 
                        }, 
                         "waist": {
                            "qpos": current_waist_action,
                            "qvel": [],
                        },
                        "base": {
                            "qpos": [],
                            "qvel": [nav_vx, nav_vy, nav_vyaw], 
                        }, 
                    }
                    if args.xr_mode == "controller":
                        states["left_trig"] = {
                            "qpos": [left_trigger_action],
                        }
                        states["right_trig"] = {
                            "qpos": [right_trigger_action],
                        }
                        actions["left_trig"] = {
                            "qpos": [left_trigger_action],
                        }
                        actions["right_trig"] = {
                            "qpos": [right_trigger_action],
                        }
                    # Hand pressures (tactiles) if available
                    tactiles = {}
                    if args.ee == "dex3":
                        if "right_press_corr" in locals(): # Defensive approach
                            tactiles["right_ee"] = right_press_corr.tolist()
                        if "left_press_corr" in locals(): # Defensive approach
                            tactiles["left_ee"] = left_press_corr.tolist()
                    torques = {}
                    if args.ee == "dex3":
                        if "right_tau" in locals():
                            torques["right_ee"] = right_tau.tolist()
                        if "left_tau" in locals():
                            torques["left_ee"] = left_tau.tolist()
                    states, actions, tactiles, torques = filter_states_actions_by_side(
                        states, actions, args.record_side, tactiles, torques
                    )
                    if args.sim:
                        sim_state = sim_state_subscriber.read_data()            
                        recorder.add_item(colors=colors, depths=depths, states=states, actions=actions, tactiles=tactiles, torques=torques, sim_state=sim_state)
                    else:
                        recorder.add_item(colors=colors, depths=depths, states=states, actions=actions, tactiles=tactiles, torques=torques)

            current_time = time.time()
            time_elapsed = current_time - start_time
            sleep_time = max(0, (1 / args.frequency) - time_elapsed)
            time.sleep(sleep_time)
            logger_mp.debug(f"main process sleep: {sleep_time}")

    except KeyboardInterrupt:
        logger_mp.info("KeyboardInterrupt, exiting program...")
    except Exception as e:
        logger_mp.error(f"Exception occurred: {type(e).__name__}: {e}")
        import traceback
        logger_mp.error(traceback.format_exc())
    finally:
        try:
            arm_ctrl.ctrl_dual_arm_go_rest()
        except Exception as e:
            logger_mp.warning(f"Failed to move arm to rest on exit: {e}")

        try:
            if args.ipc:
                if "ipc_server" in locals():
                    ipc_server.stop()
            else:
                stop_listening()
                if "listen_keyboard_thread" in locals():
                    listen_keyboard_thread.join()
        except Exception:
            pass

        try:
            if args.sim and "sim_state_subscriber" in locals():
                sim_state_subscriber.stop_subscribe()
        except Exception:
            pass

        try:
            if "tv_img_shm" in locals():
                tv_img_shm.close()
                tv_img_shm.unlink()
        except Exception:
            pass

        try:
            if "WRIST" in locals() and WRIST and "wrist_img_shm" in locals():
                wrist_img_shm.close()
                wrist_img_shm.unlink()
        except Exception:
            pass

        try:
            if args.record and "recorder" in locals():
                recorder.close()
        except Exception:
            pass
        logger_mp.info("Finally, exiting program.")
        exit(0)
