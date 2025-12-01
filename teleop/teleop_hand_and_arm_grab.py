import ctypes
import os

# 把你 conda 环境里的新版 libstdc++ 提前塞进进程，全局可见
ctypes.CDLL("/opt/miniconda3/envs/xr_tele/lib/libstdc++.so.6", mode=ctypes.RTLD_GLOBAL)


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
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__HandCmd_
# for gripper

# for simulation
from unitree_sdk2py.core.channel import ChannelPublisher
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
def publish_reset_category(category: int,publisher): # Scene Reset signal
    msg = String_(data=str(category))
    publisher.Write(msg)
    logger_mp.info(f"published reset category: {category}")

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
    parser.add_argument('--frequency', type = float, default = 30.0, help = 'save data\'s frequency')

    # basic control parameters
    parser.add_argument('--xr-mode', type=str, choices=['hand', 'controller'], default='hand', help='Select XR device tracking source')
    parser.add_argument('--arm', type=str, choices=['G1_29', 'G1_23', 'H1_2', 'H1'], default='G1_29', help='Select arm controller')
    parser.add_argument('--ee', type=str, choices=['dex1', 'dex3', 'inspire1', 'brainco', 'fake_dex'], help='Select end effector controller')
    # mode flags
    parser.add_argument('--motion', action = 'store_true', help = 'Enable motion control mode')
    parser.add_argument('--headless', action='store_true', help='Enable headless mode (no display)')
    parser.add_argument('--sim', action = 'store_true', help = 'Enable isaac simulation mode')
    parser.add_argument('--affinity', action = 'store_true', help = 'Enable high priority and set CPU affinity')
    parser.add_argument('--ipc', action = 'store_true', help = 'Enable IPC server to handle input; otherwise enable sshkeyboard')
    parser.add_argument('--record', action = 'store_true', help = 'Enable data recording')
    parser.add_argument('--record-side', type=str, choices=['both', 'left', 'right'], default='both',
                        help='Which side to store in recorded states/actions')
    parser.add_argument('--task-dir', type = str, default = './utils/data/', help = 'path to save data')
    parser.add_argument('--task-name', type = str, default = 'pick cube', help = 'task name for recording')
    parser.add_argument('--task-desc', type = str, default = 'e.g. pick the red cube on the table.', help = 'task goal for recording')

    args = parser.parse_args()
    logger_mp.info(f"args: {args}")

    record_left = args.record_side in ("left", "both")
    record_right = args.record_side in ("right", "both")

    try:
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
                'head_camera_id_numbers': [0],
                'wrist_camera_type': 'opencv',
                'wrist_camera_image_shape': [480, 640],  # Wrist camera resolution
                'wrist_camera_id_numbers': [2, 4],
            }
        else:
            img_config = {
                'fps': 30,
                'head_camera_type': 'realsense',
                'head_camera_image_shape': [480, 640],  # Head camera resolution
                'head_camera_id_numbers': ["233622072924"],
                #'wrist_camera_type': 'opencv',
                #'wrist_camera_image_shape': [480, 640],  # Wrist camera resolution
                #'wrist_camera_id_numbers': [2, 4],
            }


        ASPECT_RATIO_THRESHOLD = 2.0 # If the aspect ratio exceeds this value, it is considered binocular
        if len(img_config['head_camera_id_numbers']) > 1 or (img_config['head_camera_image_shape'][1] / img_config['head_camera_image_shape'][0] > ASPECT_RATIO_THRESHOLD):
            BINOCULAR = True
        else:
            BINOCULAR = False
        if 'wrist_camera_type' in img_config:
            WRIST = True
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
        elif WRIST and not args.sim:
            wrist_img_shape = (img_config['wrist_camera_image_shape'][0], img_config['wrist_camera_image_shape'][1] * 2, 3)
            wrist_img_shm = shared_memory.SharedMemory(create = True, size = np.prod(wrist_img_shape) * np.uint8().itemsize)
            wrist_img_array = np.ndarray(wrist_img_shape, dtype = np.uint8, buffer = wrist_img_shm.buf)
            img_client = ImageClient(tv_img_shape = tv_img_shape, tv_img_shm_name = tv_img_shm.name, 
                                    wrist_img_shape = wrist_img_shape, wrist_img_shm_name = wrist_img_shm.name)
        else:
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
            arm_ctrl = G1_29_ArmController(motion_mode=args.motion, simulation_mode=args.sim)
        elif args.arm == "G1_23":
            arm_ik = G1_23_ArmIK()
            arm_ctrl = G1_23_ArmController(motion_mode=args.motion, simulation_mode=args.sim)
        elif args.arm == "H1_2":
            arm_ik = H1_2_ArmIK()
            arm_ctrl = H1_2_ArmController(motion_mode=args.motion, simulation_mode=args.sim)
        elif args.arm == "H1":
            arm_ik = H1_ArmIK()
            arm_ctrl = H1_ArmController(simulation_mode=args.sim)

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
                                          simulation_mode=args.sim, right_hand_override=right_hand_override, left_hand_override=left_hand_override)
            
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
                logger_mp.info("Set high priority successfully.")
            except psutil.AccessDenied:
                logger_mp.warning("Failed to set high priority. Please run as root.")
                
            for child in p.children(recursive=True):
                try:
                    logger_mp.info(f"Child process {child.pid} name: {child.name()}")
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
        if args.record and args.headless:
            recorder = EpisodeWriter(task_dir = args.task_dir + args.task_name, task_goal = args.task_desc, frequency = args.frequency, rerun_log = False)
        elif args.record and not args.headless:
            recorder = EpisodeWriter(task_dir = args.task_dir + args.task_name, task_goal = args.task_desc, frequency = args.frequency, rerun_log = True)


        logger_mp.info("Please enter the start signal (enter 'r' to start the subsequent program)")
        while not START and not STOP:
            time.sleep(0.01)
        logger_mp.info("start program.")
        arm_ctrl.speed_gradual_max()

        grab_pose_right = np.array([0,-1.0,-1.0,1.4,1.3,1.4,1.3])
        grab_pose_left = np.array([0.5,1.0,1.50,-1.40,-1.60,-1.40,-1.60]) # HIVE-INFO: Original: 0,1.0,1.0,-1.4,-1.3,-1.4,-1.3
        open_pose = np.array([0.5,0,0,0,0,0,0])

        current_left_ee_action  = [0.0] * 7
        current_right_ee_action = [0.0] * 7

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
                    if args.sim:
                        publish_reset_category(2, reset_pose_publisher)
                elif key == ord('s'):
                    RECORD_TOGGLE = True
                elif key == ord('a'):
                    if args.sim:
                        publish_reset_category(2, reset_pose_publisher)

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
                    if args.sim:
                        publish_reset_category(1, reset_pose_publisher)

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

            if args.ee == "fake_dex":
                fake_q14 = np.zeros(14,dtype=np.float64)

                # if left_trigger: 
                #     fake_q14[:7] = grab_pose_left
                if left_trigger:
                    fake_q14[:7] = grab_pose_left
                else:
                    fake_q14[:7] = open_pose

                # 右手：假手，不跟扳机互动，固定张开
                fake_q14[-7:] = open_pose

                with dual_hand_data_lock:
                    dual_hand_action_array[:] = fake_q14
                    dual_hand_state_array[:] = fake_q14

                left7 = fake_q14[:7]
                for i, jid in enumerate(Dex3_1_Left_JointIndex):
                    dex3_left_msg.motor_cmd[jid].q = left7[i]
                dex3_left_pub.Write(dex3_left_msg)

                current_left_ee_action  = fake_q14[:7].tolist()
                current_right_ee_action = fake_q14[7:].tolist()
                
            elif args.ee == "dex3":
                q14 = np.array(dual_hand_action_array[:],dtype=np.float64)

                if right_trigger:
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 1.0
                    q14[-7:] = grab_pose_right
                else:
                    with right_hand_override.get_lock():
                        right_hand_override[0] = 0.0
                    q14[-7:] = open_pose
                
                if left_trigger:
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 1.0
                    q14[:7] = grab_pose_left
                else:
                    with left_hand_override.get_lock():
                        left_hand_override[0] = 0.0
                    q14[:7] = open_pose

                with dual_hand_data_lock:
                    dual_hand_action_array[:] = q14

                right7 = q14[-7:]
                for i, jid in enumerate(Dex3_1_Right_JointIndex):
                    dex3_right_msg.motor_cmd[jid].q = right7[i]
                dex3_right_pub.Write(dex3_right_msg)

                left7 = q14[:7]
                for i, jid in enumerate(Dex3_1_Left_JointIndex):
                    dex3_left_msg.motor_cmd[jid].q = left7[i]
                dex3_left_pub.Write(dex3_left_msg)

                current_left_ee_action  = q14[:7].tolist()
                current_right_ee_action = q14[7:].tolist()
            else:
                pass
            
            # record data
            if args.record:
                RECORD_READY = recorder.is_ready()
                with dual_hand_data_lock:
                    left_ee_state = dual_hand_state_array[:7]
                    right_ee_state = dual_hand_state_array[-7:]
                    # left_hand_action = dual_hand_action_array[:7]
                    # right_hand_action = dual_hand_action_array[-7:]
                    left_hand_action  = current_left_ee_action
                    right_hand_action = current_right_ee_action
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
                # apply recording-side filter
                rec_left_arm_state = left_arm_state.tolist() if record_left else []
                rec_right_arm_state = right_arm_state.tolist() if record_right else []
                rec_left_arm_action = left_arm_action.tolist() if record_left else []
                rec_right_arm_action = right_arm_action.tolist() if record_right else []
                rec_left_ee_state = left_ee_state if record_left else []
                rec_right_ee_state = right_ee_state if record_right else []
                rec_left_ee_action = left_hand_action if record_left else []
                rec_right_ee_action = right_hand_action if record_right else []
                if RECORD_RUNNING:
                    colors = {}
                    depths = {}
                    if BINOCULAR:
                        colors[f"color_{0}"] = current_tv_image[:, :tv_img_shape[1]//2]
                        colors[f"color_{1}"] = current_tv_image[:, tv_img_shape[1]//2:]
                        if WRIST:
                            colors[f"color_{2}"] = current_wrist_image[:, :wrist_img_shape[1]//2]
                            colors[f"color_{3}"] = current_wrist_image[:, wrist_img_shape[1]//2:]
                    else:
                        colors[f"color_{0}"] = current_tv_image
                        if WRIST:
                            colors[f"color_{1}"] = current_wrist_image[:, :wrist_img_shape[1]//2]
                            colors[f"color_{2}"] = current_wrist_image[:, wrist_img_shape[1]//2:]
                    states = {
                        "left_arm": {                                                                    
                            "qpos":   rec_left_arm_state,    # numpy.array -> list
                            "qvel":   [],                          
                            "torque": [],                        
                        }, 
                        "right_arm": {                                                                    
                            "qpos":   rec_right_arm_state,       
                            "qvel":   [],                          
                            "torque": [],                         
                        },                        
                        "left_ee": {                                                                    
                            "qpos":   rec_left_ee_state,           
                            "qvel":   [],                           
                            "torque": [],                          
                        }, 
                        "right_ee": {                                                                    
                            "qpos":   rec_right_ee_state,       
                            "qvel":   [],                           
                            "torque": [],  
                        }, 
                        "body": {
                            "qpos": current_body_state,
                        }, 
                    }
                    actions = {
                        "left_arm": {                                   
                            "qpos":   rec_left_arm_action,       
                            "qvel":   [],       
                            "torque": [],      
                        }, 
                        "right_arm": {                                   
                            "qpos":   rec_right_arm_action,       
                            "qvel":   [],       
                            "torque": [],       
                        },                         
                        "left_ee": {                                   
                            "qpos":   rec_left_ee_action,       
                            "qvel":   [],       
                            "torque": [],       
                        }, 
                        "right_ee": {                                   
                            "qpos":   rec_right_ee_action,       
                            "qvel":   [],       
                            "torque": [], 
                        }, 
                        "body": {
                            "qpos": current_body_action,
                        }, 
                    }
                    if args.sim:
                        sim_state = sim_state_subscriber.read_data()            
                        recorder.add_item(colors=colors, depths=depths, states=states, actions=actions, sim_state=sim_state)
                    else:
                        recorder.add_item(colors=colors, depths=depths, states=states, actions=actions)

            current_time = time.time()
            time_elapsed = current_time - start_time
            sleep_time = max(0, (1 / args.frequency) - time_elapsed)
            time.sleep(sleep_time)
            logger_mp.debug(f"main process sleep: {sleep_time}")

    except KeyboardInterrupt:
        logger_mp.info("KeyboardInterrupt, exiting program...")
    finally:
        arm_ctrl.ctrl_dual_arm_go_home()

        if args.ipc:
            ipc_server.stop()
        else:
            stop_listening()
            listen_keyboard_thread.join()

        if args.sim:
            sim_state_subscriber.stop_subscribe()
        tv_img_shm.close()
        tv_img_shm.unlink()
        if WRIST:
            wrist_img_shm.close()
            wrist_img_shm.unlink()

        if args.record:
            recorder.close()
        logger_mp.info("Finally, exiting program.")
        exit(0)
