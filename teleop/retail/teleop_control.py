import ctypes
import os

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
from teleop.robot_control.robot_arm import G1_29_ArmController
from teleop.robot_control.robot_arm_ik import G1_29_ArmIK
from teleop.robot_control.robot_hand_unitree import Dex3_1_Controller
from teleop.image_server.image_client import ImageClient
from teleop.utils.episode_writer import EpisodeWriter
from teleop.utils.ipc import IPC_Server
from sshkeyboard import listen_keyboard, stop_listening
from teleoperation.teleop.retail import teleop_config as retail_config

from teleop.robot_control.robot_hand_unitree import Dex3_1_Right_JointIndex, Dex3_1_Left_JointIndex
from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_, HandState_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__HandCmd_

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
def on_press(key):
    global STOP, START, RECORD_TOGGLE
    if key == 'r':
        START = True
    elif key == 'q':
        START = False
        STOP = True
    elif key == 's' and START == True:
        RECORD_TOGGLE = True
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
    retail_config.add_arguments(parser)

    args = parser.parse_args()
    logger_mp.info(f"args: {args}")

    try:
        def filter_states_actions_by_side(states, actions, record_side):
            if record_side == "both":
                return states, actions
            keep_prefix = "left" if record_side == "left" else "right"
            filtered_states = {key: value for key, value in states.items() if key.startswith(keep_prefix)}
            filtered_actions = {key: value for key, value in actions.items() if key.startswith(keep_prefix)}

            # keep non-side specific entries such as body
            for key, value in states.items():
                if not key.startswith(("left_", "right_")):
                    filtered_states[key] = value
            for key, value in actions.items():
                if not key.startswith(("left_", "right_")):
                    filtered_actions[key] = value
            return filtered_states, filtered_actions

        # ipc communication. client usage: see utils/ipc.py
        if args.ipc:
            ipc_server = IPC_Server(on_press=on_press, on_info=on_info, get_state=get_state)
            ipc_server.start()
        # sshkeyboard communication
        else:
            listen_keyboard_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": on_press, "until": None, "sequential": False,}, daemon=True)
            listen_keyboard_thread.start()

        # image client: img_config should be the same as the configuration in image_server.py (of Robot's development computing unit)
        img_config = retail_config.get_img_config()

        ASPECT_RATIO_THRESHOLD = retail_config.ASPECT_RATIO_THRESHOLD # If the aspect ratio exceeds this value, it is considered binocular
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

        if WRIST and WRIST_2CAM:
            print("----- dual wrist camera mode")
            wrist_img_shape = (img_config['wrist_camera_image_shape'][0], img_config['wrist_camera_image_shape'][1] * 2, 3)
            wrist_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(wrist_img_shape) * np.uint8().itemsize)
            wrist_img_array = np.ndarray(wrist_img_shape, dtype = np.uint8, buffer = wrist_img_shm.buf)
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name, 
                                    wrist_img_shape = wrist_img_shape, wrist_img_shm_name = wrist_img_shm.name)
        elif WRIST and not WRIST_2CAM:
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
                                     return_state_data=True, return_hand_rot_data = False)
        
        

        # arm
        if args.arm == "G1_29":
            arm_ik = G1_29_ArmIK()
            arm_ctrl = G1_29_ArmController(motion_mode=args.motion, simulation_mode=False, dds_interface=args.iface)

        # end-effector
        if args.ee == "dex3":
            left_hand_pos_array = Array('d', 75, lock = True)      # [input]
            right_hand_pos_array = Array('d', 75, lock = True)     # [input]
            dual_hand_data_lock = Lock()
            dual_hand_state_array = Array('d', 14, lock = False)   # [output] current left, right hand state(14) data.
            dual_hand_action_array = Array('d', 14, lock = False)  # [output] current left, right hand action(14) data.
            right_hand_override = Array('d', 1, lock = True)
            right_hand_override[0] = 0.0
            left_hand_override = Array('d', 1, lock = True)
            left_hand_override[0] = 0.0
            hand_ctrl = Dex3_1_Controller(left_hand_pos_array, right_hand_pos_array,
                                          dual_hand_data_lock, dual_hand_state_array, dual_hand_action_array, 
                                          simulation_mode=False, right_hand_override=right_hand_override, left_hand_override=left_hand_override,
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
            PRESS_BASE_N = 30  # ~1s at 30Hz

            # PER-MOTOR hold tracking (like hand_controller.py)
            right_hold_logged = [False] * 7
            left_hold_logged = [False] * 7
            right_ramped_target = np.zeros(7, dtype=np.float64)
            left_ramped_target = np.zeros(7, dtype=np.float64)

        
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

        # controller + motion mode
        if args.xr_mode == "controller" and args.motion:
            from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
            sport_client = LocoClient()
            sport_client.SetTimeout(0.0001)
            sport_client.Init()

        # record + headless mode
        if args.record and args.headless:
            recorder = EpisodeWriter(task_dir = args.task_dir + args.task_name, task_goal = args.task_desc, frequency = args.frequency, rerun_log = False)
        elif args.record and not args.headless:
            recorder = EpisodeWriter(task_dir = args.task_dir + args.task_name, task_goal = args.task_desc, frequency = args.frequency, rerun_log = True)
        if args.record:
            logger_mp.info(f"Recording side: {args.record_side}")


        logger_mp.info("Please enter the start signal (enter 'r' to start the subsequent program)")
        while not START and not STOP:
            time.sleep(0.01)
        logger_mp.info("start program.")
        arm_ctrl.speed_gradual_max()

        grab_pose_right = np.array([-0.0,-1.0,-1.70,1.55,1.75,1.55,1.75])  # Palmar grip
        grab_pose_left = np.array([0.0,1.0,1.70,-1.55,-1.75,-1.55,-1.75])  # Palmar grip
        open_pose = np.array([0,0,0,0,0,0,0])

        # --- SmartGrip parameters ---
        KP_MOVE = 1.5
        KD_MOVE = 0.2
        KP_HOLD = 0.8      # soft hold like hand_controller.py
        KD_HOLD = 0.2

        # Hysteresis thresholds (matching hand_controller.py)
        PRESSURE_THRESHOLD = 0.20              # Higher - to ENTER hold
        PRESSURE_THRESHOLD_BASE = 0.05         # Base sensor threshold (enter)
        PRESSURE_THRESHOLD_EXIT = 0.15         # Lower - to EXIT hold (sticky)
        PRESSURE_THRESHOLD_BASE_EXIT = 0.03    # Base sensor threshold (exit)
        TORQUE_THRESHOLD_HIGH = 200000.0
        
        SQUEEZE_OFFSET = 0.08     # matching hand_controller.py
        RAMP_FACTOR = 0.20        # smooth ramping
        THUMB_COMPLETION_THRESHOLD = 0.05
        
        # --- Tare (recalibration) tracking ---
        TARE_DELAY = 0.6  # seconds to wait after trigger release before taring
        right_trigger_released_time = None
        left_trigger_released_time = None
        right_trigger_prev = False
        left_trigger_prev = False
        
        # Initialize ramped targets from current hand position (prevent jumps)
        if args.ee == "dex3":
            logger_mp.info("Waiting for initial hand state...")
            time.sleep(0.5)  # Give time for state to arrive
            with dual_hand_data_lock:
                right_ramped_target[:] = np.array(dual_hand_state_array[-7:], dtype=np.float64)
                left_ramped_target[:] = np.array(dual_hand_state_array[:7], dtype=np.float64)
            # logger_mp.info(f"Initialized ramped targets - Right: {right_ramped_target}, Left: {left_ramped_target}")
        
        loop_idx = 0
        while not STOP:
            start_time = time.time()

            if not args.headless:
                tv_resized_image = cv2.resize(tv_img_array, (tv_img_shape[1] // 2, tv_img_shape[0] // 2))
                cv2.imshow("record image", tv_resized_image)
                # opencv GUI communication
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    START = False
                    STOP = True
                elif key == ord('s'):
                    RECORD_TOGGLE = True

            if args.record and RECORD_TOGGLE:
                RECORD_TOGGLE = False
                if not RECORD_RUNNING:
                    if recorder.create_episode():
                        RECORD_RUNNING = True
                    else:
                        logger_mp.error("Failed to create episode. Recording not started.")
                else:
                    RECORD_RUNNING = False
                    recorder.save_episode()

            # get input data
            tele_data = tv_wrapper.get_motion_state_data()

            if (args.ee == "dex3" or args.ee == "inspire1" or args.ee == "brainco") and args.xr_mode == "hand":
                with left_hand_pos_array.get_lock():
                    left_hand_pos_array[:] = tele_data.left_hand_pos.flatten()
                with right_hand_pos_array.get_lock():
                    right_hand_pos_array[:] = tele_data.right_hand_pos.flatten()
            # elif args.ee == "dex3"  and args.xr_mode == "controller":
            #     with left_hand_pos_array.get_lock():
            #         left_hand_pos_array[:] = tele_data.left_hand_pos.flatten()
            #     with right_hand_pos_array.get_lock():
            #         right_hand_pos_array[:] = tele_data.right_hand_pos.flatten()
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
                # control, limit velocity to within 0.3
                sport_client.Move(-tele_data.tele_state.left_thumbstick_value[1]  * 0.3,
                                  -tele_data.tele_state.left_thumbstick_value[0]  * 0.3,
                                  -tele_data.tele_state.right_thumbstick_value[0] * 0.3)

            # get current robot state data.
            current_lr_arm_q  = arm_ctrl.get_current_dual_arm_q()
            current_lr_arm_dq = arm_ctrl.get_current_dual_arm_dq()

            # solve ik using motor data and wrist pose, then use ik results to control arms.
            time_ik_start = time.time()
            sol_q, sol_tauff  = arm_ik.solve_ik(tele_data.left_arm_pose, tele_data.right_arm_pose, current_lr_arm_q, current_lr_arm_dq)
            time_ik_end = time.time()
            logger_mp.debug(f"ik:\t{round(time_ik_end - time_ik_start, 6)}")
            arm_ctrl.ctrl_dual_arm(sol_q, sol_tauff)

            right_trigger = tele_data.tele_state.right_trigger_state
            left_trigger = tele_data.tele_state.left_trigger_state
            
            # --- Detect trigger release and schedule tare ---
            current_loop_time = time.time()
            
            # Right hand: detect falling edge (was pressed, now released)
            if right_trigger_prev and not right_trigger:
                right_trigger_released_time = current_loop_time
                # logger_mp.info("[TARE] Right trigger released, will tare after delay...")
            right_trigger_prev = right_trigger
            
            # Left hand: detect falling edge
            if left_trigger_prev and not left_trigger:
                left_trigger_released_time = current_loop_time
                # logger_mp.info("[TARE] Left trigger released, will tare after delay...")
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
                    # if state not available (DDS hiccup), just keep last values
                    pass
                
                # --- Execute tare if delay has passed ---
                if right_trigger_released_time is not None:
                    if (current_loop_time - right_trigger_released_time) >= TARE_DELAY:
                        right_press_base = right_press.copy()
                        # logger_mp.info(f"[TARE] Right hand recalibrated! New baseline max: {np.max(right_press_base):.1f}")
                        right_trigger_released_time = None
                
                if left_trigger_released_time is not None:
                    if (current_loop_time - left_trigger_released_time) >= TARE_DELAY:
                        left_press_base = left_press.copy()
                        # logger_mp.info(f"[TARE] Left hand recalibrated! New baseline max: {np.max(left_press_base):.1f}")
                        left_trigger_released_time = None

                # baseline-correct and normalize (divide by 100.0 like hand_controller.py)
                PRESSURE_SCALE = 100.0
                if press_base_ready:
                    right_press_corr = np.maximum(0.0, (right_press - right_press_base) / PRESSURE_SCALE)
                    left_press_corr  = np.maximum(0.0, (left_press  - left_press_base)  / PRESSURE_SCALE)
                else:
                    right_press_corr = right_press / PRESSURE_SCALE
                    left_press_corr  = left_press / PRESSURE_SCALE

                # # --- DEBUG: print pressure and torque after calibration ---
                # if press_base_ready:
                #     if (loop_idx % args.frequency) == 0:   # ~1 Hz print
                #         print(
                #             f"[HAND DEBUG] "
                #             f"R_press_max={float(np.max(right_press_corr)):.3f} | "
                #             f"L_press_max={float(np.max(left_press_corr)):.3f} | "
                #             f"R_tau_max={float(np.max(np.abs(right_tau))):.3f} | "
                #             f"L_tau_max={float(np.max(np.abs(left_tau))):.3f}"
                #         )
                # loop_idx += 1
            


            if args.ee == "dex3":
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

                # ---------------- RIGHT hand (per-motor SmartGrip) ----------------
                if right_trigger:
                    # take ownership while gripping
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 1.0

                    # User is gripping - use palmar target with PER-MOTOR contact detection
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
                        if i == 1:  # Thumb base
                            should_hold = (right_thumb_base > thresh_main or right_thumb_tip > thresh_main or is_high_torque)
                        elif i == 2:  # Thumb tip
                            should_hold = (right_thumb_tip > thresh_main or is_high_torque)
                        elif i == 3:  # Middle base (safety link)
                            should_hold = (right_middle_base > thresh_base or right_middle_tip > thresh_main or is_high_torque)
                        elif i == 4:  # Middle tip
                            should_hold = (right_middle_tip > thresh_main or is_high_torque)
                        elif i == 5:  # Index base (safety link)
                            should_hold = (right_index_base > thresh_base or right_index_tip > thresh_main or is_high_torque)
                        elif i == 6:  # Index tip
                            should_hold = (right_index_tip > thresh_main or is_high_torque)
                        
                        if should_hold:
                            # Enter or maintain hold
                            if not right_hold_logged[i]:
                                # First contact - snap to smart target
                                direction = 1.0 if target_pose[i] > current_pos[i] else -1.0
                                smart_target = current_pos[i] + (SQUEEZE_OFFSET * direction)
                                right_ramped_target[i] = smart_target
                                logger_mp.debug(f"[RIGHT] Joint {i} contact! Snapped to {smart_target:.2f}")
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
                    
                    # Print torque values when gripping (every 10 loops ~0.33s at 30Hz)
                    # if loop_idx % 10 == 0:
                        # logger_mp.info(f"[RIGHT TORQUES] {right_tau}")

                else:
                    # Trigger released - open hand instantly (no ramping)
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 0.0

                    for i, jid in enumerate(Dex3_1_Right_JointIndex):
                        # Direct open - no ramping for faster release
                        right_ramped_target[i] = open_pose[i]
                        
                        dex3_right_msg.motor_cmd[jid].q = open_pose[i]
                        dex3_right_msg.motor_cmd[jid].kp = KP_MOVE
                        dex3_right_msg.motor_cmd[jid].kd = KD_MOVE
                        right_hold_logged[i] = False
                    
                    q14[-7:] = right_ramped_target

                # ---------------- LEFT hand (per-motor SmartGrip) ----------------
                if left_trigger:
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 1.0

                    # User is gripping - use palmar target with PER-MOTOR contact detection
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
                        if i == 1:  # Thumb base
                            should_hold = (left_thumb_base > thresh_main or left_thumb_tip > thresh_main or is_high_torque)
                        elif i == 2:  # Thumb tip
                            should_hold = (left_thumb_tip > thresh_main or is_high_torque)
                        elif i == 3:  # Middle base (safety link)
                            should_hold = (left_middle_base > thresh_base or left_middle_tip > thresh_main or is_high_torque)
                        elif i == 4:  # Middle tip
                            should_hold = (left_middle_tip > thresh_main or is_high_torque)
                        elif i == 5:  # Index base (safety link)
                            should_hold = (left_index_base > thresh_base or left_index_tip > thresh_main or is_high_torque)
                        elif i == 6:  # Index tip
                            should_hold = (left_index_tip > thresh_main or is_high_torque)
                        
                        if should_hold:
                            # Enter or maintain hold
                            if not left_hold_logged[i]:
                                # First contact - snap to smart target
                                direction = 1.0 if target_pose[i] > current_pos[i] else -1.0
                                smart_target = current_pos[i] + (SQUEEZE_OFFSET * direction)
                                left_ramped_target[i] = smart_target
                                logger_mp.debug(f"[LEFT] Joint {i} contact! Snapped to {smart_target:.2f}")
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
                    
                    # Print torque values when gripping (every 10 loops ~0.33s at 30Hz)
                    # if loop_idx % 10 == 0:
                    #     logger_mp.info(f"[LEFT TORQUES] {left_tau}")

                else:
                    # Trigger released - open hand instantly (no ramping)
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 0.0

                    for i, jid in enumerate(Dex3_1_Left_JointIndex):
                        # Direct open - no ramping for faster release
                        left_ramped_target[i] = open_pose[i]
                        
                        dex3_left_msg.motor_cmd[jid].q = open_pose[i]
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
                # dex hand or gripper
                # if args.ee == "dex3" and args.xr_mode == "hand":
                #     with dual_hand_data_lock:
                #         left_ee_state = dual_hand_state_array[:7]
                #         right_ee_state = dual_hand_state_array[-7:]
                #         left_hand_action = dual_hand_action_array[:7]
                #         right_hand_action = dual_hand_action_array[-7:]
                #         current_body_state = []
                #         current_body_action = []
                # if args.ee == "dex3" and args.xr_mode == "controller":
                #     with dual_hand_data_lock:
                #         left_ee_state = dual_hand_state_array[:7]
                #         right_ee_state = dual_hand_state_array[-7:]
                #         left_hand_action = dual_hand_action_array[:7]
                #         right_hand_action = dual_hand_action_array[-7:]
                #         current_body_state = []
                #         current_body_action = []
                # elif (args.ee == "inspire1" or args.ee == "brainco") and args.xr_mode == "hand":
                #     with dual_hand_data_lock:
                #         left_ee_state = dual_hand_state_array[:6]
                #         right_ee_state = dual_hand_state_array[-6:]
                #         left_hand_action = dual_hand_action_array[:6]
                #         right_hand_action = dual_hand_action_array[-6:]
                #         current_body_state = []
                #         current_body_action = []
                # else:
                #     left_ee_state = []
                #     right_ee_state = []
                #     left_hand_action = []
                #     right_hand_action = []
                #     current_body_state = []
                #     current_body_action = []
                with dual_hand_data_lock:
                    left_ee_state = dual_hand_state_array[:7]
                    right_ee_state = dual_hand_state_array[-7:]
                    left_hand_action = dual_hand_action_array[:7]
                    right_hand_action = dual_hand_action_array[-7:]
                    current_body_state = []
                    current_body_action = []
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
                        "body": {
                            "qpos": current_body_state,
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
                        "body": {
                            "qpos": current_body_action,
                        }, 
                    }
                    states, actions = filter_states_actions_by_side(states, actions, args.record_side)
                    recorder.add_item(colors=colors, depths=depths, states=states, actions=actions)

            current_time = time.time()
            time_elapsed = current_time - start_time
            sleep_time = max(0, (1 / args.frequency) - time_elapsed)
            time.sleep(sleep_time)
            logger_mp.debug(f"main process sleep: {sleep_time}")

    except KeyboardInterrupt:
        logger_mp.info("KeyboardInterrupt, exiting program...")
    finally:
        #arm_ctrl.ctrl_dual_arm_go_home()

        if args.ipc:
            ipc_server.stop()
        else:
            stop_listening()
            listen_keyboard_thread.join()

        tv_img_shm.close()
        tv_img_shm.unlink()
        if WRIST:
            wrist_img_shm.close()
            wrist_img_shm.unlink()

        if args.record:
            recorder.close()
        logger_mp.info("Finally, exiting program.")
        exit(0)
