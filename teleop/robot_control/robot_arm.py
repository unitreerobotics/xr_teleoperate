import numpy as np
import threading
import time
from enum import IntEnum

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize # dds
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import ( LowCmd_  as hg_LowCmd, LowState_ as hg_LowState) # idl for g1, h1_2
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC

from unitree_sdk2py.idl.unitree_go.msg.dds_ import ( LowCmd_  as go_LowCmd, LowState_ as go_LowState)  # idl for h1
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_

import logging_mp
logger_mp = logging_mp.getLogger(__name__)

from teleop.robot_control.dds_utils import wait_for_dds

kTopicLowCommand_Debug  = "rt/lowcmd"
kTopicLowCommand_Motion = "rt/arm_sdk"
kTopicLowState = "rt/lowstate"

G1_29_Num_Motors = 35
G1_23_Num_Motors = 35
H1_2_Num_Motors = 35
H1_Num_Motors = 20
H2_Num_Motors = 35
R1_A5_Num_Motors = 35
R1_A7_Num_Motors = 35
 

class MotorState:
    def __init__(self):
        self.q = None
        self.dq = None

class G1_29_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(G1_29_Num_Motors)]

class G1_23_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(G1_23_Num_Motors)]

class H1_2_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(H1_2_Num_Motors)]

class H1_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(H1_Num_Motors)]

class H2_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(H2_Num_Motors)]

class R1_A5_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(R1_A5_Num_Motors)]

class R1_A7_LowState:
    def __init__(self):
        self.motor_state = [MotorState() for _ in range(R1_A7_Num_Motors)]


class DataBuffer:
    def __init__(self):
        self.data = None
        self.lock = threading.Lock()

    def GetData(self):
        with self.lock:
            return self.data

    def SetData(self, data):
        with self.lock:
            self.data = data

class G1_29_ArmController:
    def __init__(self, motion_mode = False, simulation_mode = False):
        logger_mp.info("Initialize G1_29_ArmController...")
        self.q_target = np.zeros(14)
        self.tauff_target = np.zeros(14)
        self.motion_mode = motion_mode
        self.simulation_mode = simulation_mode
        self.kp_high = 300.0
        self.kd_high = 3.0
        self.kp_low = 80.0
        self.kd_low = 3.0
        self.kp_wrist = 40.0
        self.kd_wrist = 1.5

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0
        # Fixed-base teleoperation uses the waist to reach the Ridgeback on
        # either side.  Stay comfortably inside G1's mechanical joint limit
        # while allowing substantially more torso rotation than before.
        self.waist_yaw_limit = 2.00
        self.waist_yaw_velocity_limit = 1.25
        self.waist_yaw_input_rate = 1.8
        self.waist_yaw_target = 0.0
        self._waist_yaw_command = 0.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None

        # Isaac Sim listens on rt/lowcmd; rt/arm_sdk is the real robot's
        # motion-mode upper-body channel.
        if self.motion_mode and not self.simulation_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "G1_29_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        self.waist_yaw_target = float(self.all_motor_q[G1_29_JointIndex.kWaistYaw])
        self._waist_yaw_command = self.waist_yaw_target
        logger_mp.debug(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.debug(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms...")

        arm_indices = set(member.value for member in G1_29_JointArmIndex)
        for id in G1_29_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize G1_29_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = G1_29_LowState()
                for id in range(G1_29_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[G1_29_JointIndex.kNotUsedJoint0].q = 1.0;

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(G1_29_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]   

            # Smooth, position-based Quest right-stick control for waist yaw.
            waist_delta = np.clip(
                self.waist_yaw_target - self._waist_yaw_command,
                -self.waist_yaw_velocity_limit * self.control_dt,
                self.waist_yaw_velocity_limit * self.control_dt,
            )
            self._waist_yaw_command += waist_delta
            waist_cmd = self.msg.motor_cmd[G1_29_JointIndex.kWaistYaw]
            waist_cmd.q = self._waist_yaw_command
            waist_cmd.dq = 0.0
            waist_cmd.tau = 0.0

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)
            # logger_mp.debug(f"arm_velocity_limit:{self.arm_velocity_limit}")
            # logger_mp.debug(f"sleep_time:{sleep_time}")

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def set_waist_yaw_input(self, axis_x):
        """Integrate Quest right-stick input and hold angle when released."""
        axis_x = float(axis_x)
        if abs(axis_x) < 0.04:
            return
        self.waist_yaw_target = float(np.clip(
            self.waist_yaw_target - axis_x * self.waist_yaw_input_rate / 30.0,
            -self.waist_yaw_limit,
            self.waist_yaw_limit,
        ))

    def get_waist_yaw_command(self):
        """Return the smoothed waist command used by hierarchical body turning."""
        return float(self._waist_yaw_command)

    def get_mode_machine(self):
        '''Return current dds mode machine.'''
        return self.lowstate_subscriber.Read().mode_machine
    
    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in G1_29_JointIndex])
    
    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in G1_29_JointArmIndex])
    
    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in G1_29_JointArmIndex])
    
    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[G1_29_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(14)
            # self.tauff_target = np.zeros(14)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[G1_29_JointIndex.kNotUsedJoint0].q = weight;
                        time.sleep(0.02)
                logger_mp.info("[G1_29_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            G1_29_JointIndex.kLeftAnklePitch.value,
            G1_29_JointIndex.kRightAnklePitch.value,
            # Left arm
            G1_29_JointIndex.kLeftShoulderPitch.value,
            G1_29_JointIndex.kLeftShoulderRoll.value,
            G1_29_JointIndex.kLeftShoulderYaw.value,
            G1_29_JointIndex.kLeftElbow.value,
            # Right arm
            G1_29_JointIndex.kRightShoulderPitch.value,
            G1_29_JointIndex.kRightShoulderRoll.value,
            G1_29_JointIndex.kRightShoulderYaw.value,
            G1_29_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors
    
    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            G1_29_JointIndex.kLeftWristRoll.value,
            G1_29_JointIndex.kLeftWristPitch.value,
            G1_29_JointIndex.kLeftWristyaw.value,
            G1_29_JointIndex.kRightWristRoll.value,
            G1_29_JointIndex.kRightWristPitch.value,
            G1_29_JointIndex.kRightWristYaw.value,
        ]
        return motor_index.value in wrist_motors

class G1_29_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28

class G1_29_JointIndex(IntEnum):
    # Left leg
    kLeftHipPitch = 0
    kLeftHipRoll = 1
    kLeftHipYaw = 2
    kLeftKnee = 3
    kLeftAnklePitch = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipPitch = 6
    kRightHipRoll = 7
    kRightHipYaw = 8
    kRightKnee = 9
    kRightAnklePitch = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12
    kWaistRoll = 13
    kWaistPitch = 14

    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28
    
    # not used
    kNotUsedJoint0 = 29
    kNotUsedJoint1 = 30
    kNotUsedJoint2 = 31
    kNotUsedJoint3 = 32
    kNotUsedJoint4 = 33
    kNotUsedJoint5 = 34

class G1_23_ArmController:
    def __init__(self, motion_mode = False, simulation_mode = False):
        self.simulation_mode = simulation_mode
        self.motion_mode = motion_mode

        logger_mp.info("Initialize G1_23_ArmController...")
        self.q_target = np.zeros(10)
        self.tauff_target = np.zeros(10)

        self.kp_high = 300.0
        self.kd_high = 3.0
        self.kp_low = 80.0
        self.kd_low = 3.0
        self.kp_wrist = 40.0
        self.kd_wrist = 1.5

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None

        
        if self.motion_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "G1_23_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.info(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.info(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms...")

        arm_indices = set(member.value for member in G1_23_JointArmIndex)
        for id in G1_23_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize G1_23_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = G1_23_LowState()
                for id in range(G1_23_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[G1_23_JointIndex.kNotUsedJoint0].q = 1.0;

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(G1_23_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]      

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)
            # logger_mp.debug(f"arm_velocity_limit:{self.arm_velocity_limit}")
            # logger_mp.debug(f"sleep_time:{sleep_time}")

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def get_mode_machine(self):
        '''Return current dds mode machine.'''
        return self.lowstate_subscriber.Read().mode_machine
    
    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in G1_23_JointIndex])
    
    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in G1_23_JointArmIndex])
    
    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in G1_23_JointArmIndex])
    
    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[G1_23_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(10)
            # self.tauff_target = np.zeros(10)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[G1_23_JointIndex.kNotUsedJoint0].q = weight;
                        time.sleep(0.02)
                logger_mp.info("[G1_23_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            G1_23_JointIndex.kLeftAnklePitch.value,
            G1_23_JointIndex.kRightAnklePitch.value,
            # Left arm
            G1_23_JointIndex.kLeftShoulderPitch.value,
            G1_23_JointIndex.kLeftShoulderRoll.value,
            G1_23_JointIndex.kLeftShoulderYaw.value,
            G1_23_JointIndex.kLeftElbow.value,
            # Right arm
            G1_23_JointIndex.kRightShoulderPitch.value,
            G1_23_JointIndex.kRightShoulderRoll.value,
            G1_23_JointIndex.kRightShoulderYaw.value,
            G1_23_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors
    
    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            G1_23_JointIndex.kLeftWristRoll.value,
            G1_23_JointIndex.kRightWristRoll.value,
        ]
        return motor_index.value in wrist_motors

class G1_23_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26

class G1_23_JointIndex(IntEnum):
    # Left leg
    kLeftHipPitch = 0
    kLeftHipRoll = 1
    kLeftHipYaw = 2
    kLeftKnee = 3
    kLeftAnklePitch = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipPitch = 6
    kRightHipRoll = 7
    kRightHipYaw = 8
    kRightKnee = 9
    kRightAnklePitch = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12
    kWaistRollNotUsed = 13
    kWaistPitchNotUsed = 14

    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitchNotUsed = 20
    kLeftWristyawNotUsed = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitchNotUsed = 27
    kRightWristYawNotUsed = 28
    
    # not used
    kNotUsedJoint0 = 29
    kNotUsedJoint1 = 30
    kNotUsedJoint2 = 31
    kNotUsedJoint3 = 32
    kNotUsedJoint4 = 33
    kNotUsedJoint5 = 34

class H1_2_ArmController:
    def __init__(self, motion_mode = False, simulation_mode = False):
        self.simulation_mode = simulation_mode
        self.motion_mode = motion_mode
        
        logger_mp.info("Initialize H1_2_ArmController...")
        self.q_target = np.zeros(14)
        self.tauff_target = np.zeros(14)

        self.kp_high = 300.0
        self.kd_high = 5.0
        self.kp_low = 140.0
        self.kd_low = 3.0
        self.kp_wrist = 50.0
        self.kd_wrist = 2.0

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None


        if self.motion_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "H1_2_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.info(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.info(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms...")

        arm_indices = set(member.value for member in H1_2_JointArmIndex)
        for id in H1_2_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize H1_2_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = H1_2_LowState()
                for id in range(H1_2_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[H1_2_JointIndex.kNotUsedJoint0].q = 1.0;

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(H1_2_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]      

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)
            # logger_mp.debug(f"arm_velocity_limit:{self.arm_velocity_limit}")
            # logger_mp.debug(f"sleep_time:{sleep_time}")

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def get_mode_machine(self):
        '''Return current dds mode machine.'''
        return self.lowstate_subscriber.Read().mode_machine
    
    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H1_2_JointIndex])
    
    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H1_2_JointArmIndex])
    
    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in H1_2_JointArmIndex])
    
    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[H1_2_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(14)
            # self.tauff_target = np.zeros(14)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[H1_2_JointIndex.kNotUsedJoint0].q = weight;
                        time.sleep(0.02)
                logger_mp.info("[H1_2_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            H1_2_JointIndex.kLeftAnkle.value,
            H1_2_JointIndex.kRightAnkle.value,
            # Left arm
            H1_2_JointIndex.kLeftShoulderPitch.value,
            H1_2_JointIndex.kLeftShoulderRoll.value,
            H1_2_JointIndex.kLeftShoulderYaw.value,
            H1_2_JointIndex.kLeftElbowPitch.value,
            # Right arm
            H1_2_JointIndex.kRightShoulderPitch.value,
            H1_2_JointIndex.kRightShoulderRoll.value,
            H1_2_JointIndex.kRightShoulderYaw.value,
            H1_2_JointIndex.kRightElbowPitch.value,
        ]
        return motor_index.value in weak_motors
    
    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            H1_2_JointIndex.kLeftElbowRoll.value,
            H1_2_JointIndex.kLeftWristPitch.value,
            H1_2_JointIndex.kLeftWristyaw.value,
            H1_2_JointIndex.kRightElbowRoll.value,
            H1_2_JointIndex.kRightWristPitch.value,
            H1_2_JointIndex.kRightWristYaw.value,
        ]
        return motor_index.value in wrist_motors
    
class H1_2_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 13
    kLeftShoulderRoll = 14
    kLeftShoulderYaw = 15
    kLeftElbowPitch = 16
    kLeftElbowRoll = 17
    kLeftWristPitch = 18
    kLeftWristyaw = 19

    # Right arm
    kRightShoulderPitch = 20
    kRightShoulderRoll = 21
    kRightShoulderYaw = 22
    kRightElbowPitch = 23
    kRightElbowRoll = 24
    kRightWristPitch = 25
    kRightWristYaw = 26

class H1_2_JointIndex(IntEnum):
    # Left leg
    kLeftHipYaw = 0
    kLeftHipRoll = 1
    kLeftHipPitch = 2
    kLeftKnee = 3
    kLeftAnkle = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipYaw = 6
    kRightHipRoll = 7
    kRightHipPitch = 8
    kRightKnee = 9
    kRightAnkle = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12

    # Left arm
    kLeftShoulderPitch = 13
    kLeftShoulderRoll = 14
    kLeftShoulderYaw = 15
    kLeftElbowPitch = 16
    kLeftElbowRoll = 17
    kLeftWristPitch = 18
    kLeftWristyaw = 19

    # Right arm
    kRightShoulderPitch = 20
    kRightShoulderRoll = 21
    kRightShoulderYaw = 22
    kRightElbowPitch = 23
    kRightElbowRoll = 24
    kRightWristPitch = 25
    kRightWristYaw = 26

    kNotUsedJoint0 = 27
    kNotUsedJoint1 = 28
    kNotUsedJoint2 = 29
    kNotUsedJoint3 = 30
    kNotUsedJoint4 = 31
    kNotUsedJoint5 = 32
    kNotUsedJoint6 = 33
    kNotUsedJoint7 = 34

class H1_ArmController:
    def __init__(self, simulation_mode = False):
        self.simulation_mode = simulation_mode
        
        logger_mp.info("Initialize H1_ArmController...")
        self.q_target = np.zeros(8)
        self.tauff_target = np.zeros(8)

        self.kp_high = 300.0
        self.kd_high = 5.0
        self.kp_low = 140.0
        self.kd_low = 3.0

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None

        self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, go_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, go_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "H1_ArmController")

        # initialize h1's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_go_msg_dds__LowCmd_()
        self.msg.head[0] = 0xFE
        self.msg.head[1] = 0xEF
        self.msg.level_flag = 0xFF
        self.msg.gpio = 0

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.info(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.info(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms...")

        for id in H1_JointIndex:
            if self._Is_weak_motor(id):
                self.msg.motor_cmd[id].kp = self.kp_low
                self.msg.motor_cmd[id].kd = self.kd_low
                self.msg.motor_cmd[id].mode = 0x01
            else:
                self.msg.motor_cmd[id].kp = self.kp_high
                self.msg.motor_cmd[id].kd = self.kd_high
                self.msg.motor_cmd[id].mode = 0x0A
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize H1_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = H1_LowState()
                for id in range(H1_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def _ctrl_motor_state(self):
        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(H1_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]      

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)
            # logger_mp.debug(f"arm_velocity_limit:{self.arm_velocity_limit}")
            # logger_mp.debug(f"sleep_time:{sleep_time}")

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target
    
    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H1_JointIndex])
    
    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H1_JointArmIndex])
    
    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in H1_JointArmIndex])
    
    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[H1_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(8)
            # self.tauff_target = np.zeros(8)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                logger_mp.info("[H1_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            H1_JointIndex.kLeftAnkle.value,
            H1_JointIndex.kRightAnkle.value,
            # Left arm
            H1_JointIndex.kLeftShoulderPitch.value,
            H1_JointIndex.kLeftShoulderRoll.value,
            H1_JointIndex.kLeftShoulderYaw.value,
            H1_JointIndex.kLeftElbow.value,
            # Right arm
            H1_JointIndex.kRightShoulderPitch.value,
            H1_JointIndex.kRightShoulderRoll.value,
            H1_JointIndex.kRightShoulderYaw.value,
            H1_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors
    
class H1_JointArmIndex(IntEnum):
    # Unlike G1 and H1_2, the arm order in DDS messages for H1 is right then left. 
    # Therefore, the purpose of switching the order here is to maintain consistency with G1 and H1_2.
    # Left arm
    kLeftShoulderPitch = 16
    kLeftShoulderRoll = 17
    kLeftShoulderYaw = 18
    kLeftElbow = 19
    # Right arm
    kRightShoulderPitch = 12
    kRightShoulderRoll = 13
    kRightShoulderYaw = 14
    kRightElbow = 15

class H1_JointIndex(IntEnum):
    kRightHipRoll = 0
    kRightHipPitch = 1
    kRightKnee = 2
    kLeftHipRoll = 3
    kLeftHipPitch = 4
    kLeftKnee = 5
    kWaistYaw = 6
    kLeftHipYaw = 7
    kRightHipYaw = 8
    kNotUsedJoint = 9
    kLeftAnkle = 10
    kRightAnkle = 11
    # Right arm
    kRightShoulderPitch = 12
    kRightShoulderRoll = 13
    kRightShoulderYaw = 14
    kRightElbow = 15
    # Left arm
    kLeftShoulderPitch = 16
    kLeftShoulderRoll = 17
    kLeftShoulderYaw = 18
    kLeftElbow = 19

class H2_ArmController:
    def __init__(self, motion_mode=False, simulation_mode=False):
        logger_mp.info("Initialize H2_ArmController...")
        self.q_target = np.zeros(14)
        self.tauff_target = np.zeros(14)
        self.motion_mode = motion_mode
        self.simulation_mode = simulation_mode
        self.kp_high = 300.0
        self.kd_high = 5.0
        self.kp_low = 140.0
        self.kd_low = 3.0
        self.kp_wrist = 50.0
        self.kd_wrist = 2.0

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None
        
        if self.motion_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "H2_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.debug(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.debug(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms...")

        arm_indices = set(member.value for member in H2_JointArmIndex)
        for id in H2_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            logger_mp.info(
                f"Motor {id.value} ({id.name}): kp={self.msg.motor_cmd[id].kp}, kd={self.msg.motor_cmd[id].kd}"
            )
            self.msg.motor_cmd[id].q = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize H2_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = H2_LowState()
                for id in range(35):
                    lowstate.motor_state[id].q = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[H2_JointIndex.kNotUsedJoint0].q = 1.0

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit=self.arm_velocity_limit)

            for idx, id in enumerate(H2_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)

    def ctrl_dual_arm(self, q_target, tauff_target):
        """Set control target values q & tau of the left and right arm motors."""
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def get_mode_machine(self):
        """Return current dds mode machine."""
        return self.lowstate_subscriber.Read().mode_machine

    def get_current_motor_q(self):
        """Return current state q of all body motors."""
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H2_JointIndex])

    def get_current_dual_arm_q(self):
        """Return current state q of the left and right arm motors."""
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in H2_JointArmIndex])

    def get_current_dual_arm_dq(self):
        """Return current state dq of the left and right arm motors."""
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in H2_JointArmIndex])

    def ctrl_dual_arm_go_home(self):
        """Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero."""
        logger_mp.info("[H2_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(14)
        tolerance = 0.05
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[H2_JointIndex.kNotUsedJoint0].q = weight
                        time.sleep(0.02)
                logger_mp.info("[H2_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t=5.0):
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            H2_JointIndex.kLeftAnklePitch.value,
            H2_JointIndex.kRightAnklePitch.value,
            # Left arm
            H2_JointIndex.kLeftShoulderPitch.value,
            H2_JointIndex.kLeftShoulderRoll.value,
            H2_JointIndex.kLeftShoulderYaw.value,
            H2_JointIndex.kLeftElbow.value,
            # Right arm
            H2_JointIndex.kRightShoulderPitch.value,
            H2_JointIndex.kRightShoulderRoll.value,
            H2_JointIndex.kRightShoulderYaw.value,
            H2_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors

    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            H2_JointIndex.kLeftWristRoll.value,
            H2_JointIndex.kLeftWristPitch.value,
            H2_JointIndex.kLeftWristyaw.value,
            H2_JointIndex.kRightWristRoll.value,
            H2_JointIndex.kRightWristPitch.value,
            H2_JointIndex.kRightWristYaw.value,
        ]
        return motor_index.value in wrist_motors

class H2_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28


class H2_JointIndex(IntEnum):
    # Left leg
    kLeftHipPitch = 0
    kLeftHipRoll = 1
    kLeftHipYaw = 2
    kLeftKnee = 3
    kLeftAnklePitch = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipPitch = 6
    kRightHipRoll = 7
    kRightHipYaw = 8
    kRightKnee = 9
    kRightAnklePitch = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12
    kWaistRoll = 13
    kWaistPitch = 14

    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28

    # Head
    kHeadPitch = 29
    kHeadYaw = 30

    # not used
    kNotUsedJoint0 = 31
    kNotUsedJoint1 = 32
    kNotUsedJoint2 = 33
    kNotUsedJoint3 = 34

class R1_A5_ArmController:
    def __init__(self, motion_mode = False, simulation_mode = False):
        logger_mp.info("Initialize R1_A5_ArmController...")
        self.q_target = np.zeros(10)
        self.tauff_target = np.zeros(10)
        self.motion_mode = motion_mode
        self.simulation_mode = simulation_mode
        self.kp_high = 300.0
        self.kd_high = 3.0
        self.kp_low = 80.0
        self.kd_low = 3.0
        self.kp_wrist = 40.0
        self.kd_wrist = 1.5
        self.kp_head = 40.0
        self.kd_head = 1.5

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None

        if self.motion_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "R1_A5_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.debug(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.debug(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms and head...")

        arm_indices = set(member.value for member in R1_A5_JointArmIndex)
        head_indices = set(member.value for member in R1_A5_JointHeadIndex)
        for id in R1_A5_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            elif id.value in head_indices:
                self.msg.motor_cmd[id].kp = self.kp_head
                self.msg.motor_cmd[id].kd = self.kd_head
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # head pitch/yaw gradually return to zero at startup
        self.ctrl_head_go_home()

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize R1_A5_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = R1_A5_LowState()
                for id in range(R1_A5_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def ctrl_head_go_home(self, duration = 3.0):
        '''At startup, linearly move head pitch/yaw from their current position to zero over `duration` seconds.'''
        logger_mp.info("[R1_A5_ArmController] head returning to zero...")
        start_q = self.get_current_head_q()
        steps = max(1, int(duration / self.control_dt))
        for step in range(1, steps + 1):
            head_q = start_q * (1.0 - step / steps)   # linear ramp to zero
            for idx, id in enumerate(R1_A5_JointHeadIndex):
                self.msg.motor_cmd[id].q = head_q[idx]
            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)
            time.sleep(self.control_dt)
        logger_mp.info("[R1_A5_ArmController] head return to zero OK!")

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[R1_A5_JointIndex.kNotUsedJoint0].q = 1.0;

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(R1_A5_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def get_mode_machine(self):
        '''Return current dds mode machine.'''
        return self.lowstate_subscriber.Read().mode_machine

    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A5_JointIndex])

    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A5_JointArmIndex])

    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in R1_A5_JointArmIndex])

    def get_current_head_q(self):
        '''Return current state q of the head pitch/yaw motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A5_JointHeadIndex])

    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[R1_A5_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(10)
            # self.tauff_target = np.zeros(10)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[R1_A5_JointIndex.kNotUsedJoint0].q = weight;
                        time.sleep(0.02)
                logger_mp.info("[R1_A5_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            R1_A5_JointIndex.kLeftAnklePitch.value,
            R1_A5_JointIndex.kRightAnklePitch.value,
            # Left arm
            R1_A5_JointIndex.kLeftShoulderPitch.value,
            R1_A5_JointIndex.kLeftShoulderRoll.value,
            R1_A5_JointIndex.kLeftShoulderYaw.value,
            R1_A5_JointIndex.kLeftElbow.value,
            # Right arm
            R1_A5_JointIndex.kRightShoulderPitch.value,
            R1_A5_JointIndex.kRightShoulderRoll.value,
            R1_A5_JointIndex.kRightShoulderYaw.value,
            R1_A5_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors

    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            R1_A5_JointIndex.kLeftWristRoll.value,
            R1_A5_JointIndex.kRightWristRoll.value,
        ]
        return motor_index.value in wrist_motors

class R1_A5_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26

class R1_A5_JointHeadIndex(IntEnum):
    kHeadPitch = 29
    kHeadYaw = 30

class R1_A5_JointIndex(IntEnum):
    # Left leg
    kLeftHipPitch = 0
    kLeftHipRoll = 1
    kLeftHipYaw = 2
    kLeftKnee = 3
    kLeftAnklePitch = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipPitch = 6
    kRightHipRoll = 7
    kRightHipYaw = 8
    kRightKnee = 9
    kRightAnklePitch = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12
    kWaistRollNotUsed = 13
    kWaistPitchNotUsed = 14

    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitchNotUsed = 20
    kLeftWristyawNotUsed = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitchNotUsed = 27
    kRightWristYawNotUsed = 28

    # Head
    kHeadPitch = 29
    kHeadYaw = 30

    # not used
    kNotUsedJoint0 = 31
    kNotUsedJoint1 = 32
    kNotUsedJoint2 = 33
    kNotUsedJoint3 = 34

class R1_A7_ArmController:
    def __init__(self, motion_mode = False, simulation_mode = False):
        logger_mp.info("Initialize R1_A7_ArmController...")
        self.q_target = np.zeros(14)
        self.tauff_target = np.zeros(14)
        self.motion_mode = motion_mode
        self.simulation_mode = simulation_mode
        self.kp_high = 300.0
        self.kd_high = 3.0
        self.kp_low = 80.0
        self.kd_low = 3.0
        self.kp_wrist = 40.0
        self.kd_wrist = 1.5
        self.kp_head = 40.0
        self.kd_head = 1.5

        self.all_motor_q = None
        self.arm_velocity_limit = 20.0
        self.control_dt = 1.0 / 250.0

        self._speed_gradual_max = False
        self._gradual_start_time = None
        self._gradual_time = None

        if self.motion_mode:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Motion, hg_LowCmd)
        else:
            self.lowcmd_publisher = ChannelPublisher(kTopicLowCommand_Debug, hg_LowCmd)
        self.lowcmd_publisher.Init()
        self.lowstate_subscriber = ChannelSubscriber(kTopicLowState, hg_LowState)
        self.lowstate_subscriber.Init()
        self.lowstate_buffer = DataBuffer()
        self.lowstate_sub_ready = False

        # initialize subscribe thread
        self.subscribe_thread = threading.Thread(target=self._subscribe_motor_state)
        self.subscribe_thread.daemon = True
        self.subscribe_thread.start()

        wait_for_dds(lambda: self.lowstate_sub_ready, "R1_A7_ArmController")

        # initialize hg's lowcmd msg
        self.crc = CRC()
        self.msg = unitree_hg_msg_dds__LowCmd_()
        self.msg.mode_pr = 0
        self.msg.mode_machine = self.get_mode_machine()

        self.all_motor_q = self.get_current_motor_q()
        logger_mp.debug(f"Current all body motor state q:\n{self.all_motor_q} \n")
        logger_mp.debug(f"Current two arms motor state q:\n{self.get_current_dual_arm_q()}\n")
        logger_mp.info("Lock all joints except two arms and head...")

        arm_indices = set(member.value for member in R1_A7_JointArmIndex)
        head_indices = set(member.value for member in R1_A7_JointHeadIndex)
        for id in R1_A7_JointIndex:
            self.msg.motor_cmd[id].mode = 1
            if id.value in arm_indices:
                if self._Is_wrist_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_wrist
                    self.msg.motor_cmd[id].kd = self.kd_wrist
                else:
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
            elif id.value in head_indices:
                self.msg.motor_cmd[id].kp = self.kp_head
                self.msg.motor_cmd[id].kd = self.kd_head
            else:
                if self._Is_weak_motor(id):
                    self.msg.motor_cmd[id].kp = self.kp_low
                    self.msg.motor_cmd[id].kd = self.kd_low
                else:
                    self.msg.motor_cmd[id].kp = self.kp_high
                    self.msg.motor_cmd[id].kd = self.kd_high
            self.msg.motor_cmd[id].q  = self.all_motor_q[id]
        logger_mp.info("Lock OK!")

        # head pitch/yaw gradually return to zero at startup
        self.ctrl_head_go_home()

        # initialize publish thread
        self.publish_thread = threading.Thread(target=self._ctrl_motor_state)
        self.ctrl_lock = threading.Lock()
        self.publish_thread.daemon = True
        self.publish_thread.start()

        logger_mp.info("Initialize R1_A7_ArmController OK!")

    def _subscribe_motor_state(self):
        while True:
            msg = self.lowstate_subscriber.Read()
            if msg is not None:
                lowstate = R1_A7_LowState()
                for id in range(R1_A7_Num_Motors):
                    lowstate.motor_state[id].q  = msg.motor_state[id].q
                    lowstate.motor_state[id].dq = msg.motor_state[id].dq
                self.lowstate_buffer.SetData(lowstate)
                self.lowstate_sub_ready = True
            time.sleep(0.002)

    def clip_arm_q_target(self, target_q, velocity_limit):
        current_q = self.get_current_dual_arm_q()
        delta = target_q - current_q
        motion_scale = np.max(np.abs(delta)) / (velocity_limit * self.control_dt)
        cliped_arm_q_target = current_q + delta / max(motion_scale, 1.0)
        return cliped_arm_q_target

    def ctrl_head_go_home(self, duration = 3.0):
        '''At startup, linearly move head pitch/yaw from their current position to zero over `duration` seconds.'''
        logger_mp.info("[R1_A7_ArmController] head returning to zero...")
        start_q = self.get_current_head_q()
        steps = max(1, int(duration / self.control_dt))
        for step in range(1, steps + 1):
            head_q = start_q * (1.0 - step / steps)   # linear ramp to zero
            for idx, id in enumerate(R1_A7_JointHeadIndex):
                self.msg.motor_cmd[id].q = head_q[idx]
            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)
            time.sleep(self.control_dt)
        logger_mp.info("[R1_A7_ArmController] head return to zero OK!")

    def _ctrl_motor_state(self):
        if self.motion_mode:
            self.msg.motor_cmd[R1_A7_JointIndex.kNotUsedJoint0].q = 1.0;

        while True:
            start_time = time.time()

            with self.ctrl_lock:
                arm_q_target     = self.q_target
                arm_tauff_target = self.tauff_target

            if self.simulation_mode:
                cliped_arm_q_target = arm_q_target
            else:
                cliped_arm_q_target = self.clip_arm_q_target(arm_q_target, velocity_limit = self.arm_velocity_limit)

            for idx, id in enumerate(R1_A7_JointArmIndex):
                self.msg.motor_cmd[id].q = cliped_arm_q_target[idx]
                self.msg.motor_cmd[id].dq = 0
                self.msg.motor_cmd[id].tau = arm_tauff_target[idx]

            self.msg.crc = self.crc.Crc(self.msg)
            self.lowcmd_publisher.Write(self.msg)

            if self._speed_gradual_max is True:
                t_elapsed = start_time - self._gradual_start_time
                self.arm_velocity_limit = 20.0 + (10.0 * min(1.0, t_elapsed / 5.0))

            current_time = time.time()
            all_t_elapsed = current_time - start_time
            sleep_time = max(0, (self.control_dt - all_t_elapsed))
            time.sleep(sleep_time)

    def ctrl_dual_arm(self, q_target, tauff_target):
        '''Set control target values q & tau of the left and right arm motors.'''
        with self.ctrl_lock:
            self.q_target = q_target
            self.tauff_target = tauff_target

    def get_mode_machine(self):
        '''Return current dds mode machine.'''
        return self.lowstate_subscriber.Read().mode_machine

    def get_current_motor_q(self):
        '''Return current state q of all body motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A7_JointIndex])

    def get_current_dual_arm_q(self):
        '''Return current state q of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A7_JointArmIndex])

    def get_current_dual_arm_dq(self):
        '''Return current state dq of the left and right arm motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].dq for id in R1_A7_JointArmIndex])

    def get_current_head_q(self):
        '''Return current state q of the head pitch/yaw motors.'''
        return np.array([self.lowstate_buffer.GetData().motor_state[id].q for id in R1_A7_JointHeadIndex])

    def ctrl_dual_arm_go_home(self):
        '''Move both the left and right arms of the robot to their home position by setting the target joint angles (q) and torques (tau) to zero.'''
        logger_mp.info("[R1_A7_ArmController] ctrl_dual_arm_go_home start...")
        max_attempts = 100
        current_attempts = 0
        with self.ctrl_lock:
            self.q_target = np.zeros(14)
            # self.tauff_target = np.zeros(14)
        tolerance = 0.05  # Tolerance threshold for joint angles to determine "close to zero", can be adjusted based on your motor's precision requirements
        while current_attempts < max_attempts:
            current_q = self.get_current_dual_arm_q()
            if np.all(np.abs(current_q) < tolerance):
                if self.motion_mode:
                    for weight in np.linspace(1, 0, num=101):
                        self.msg.motor_cmd[R1_A7_JointIndex.kNotUsedJoint0].q = weight;
                        time.sleep(0.02)
                logger_mp.info("[R1_A7_ArmController] both arms have reached the home position.")
                break
            current_attempts += 1
            time.sleep(0.05)

    def speed_gradual_max(self, t = 5.0):
        '''Parameter t is the total time required for arms velocity to gradually increase to its maximum value, in seconds. The default is 5.0.'''
        self._gradual_start_time = time.time()
        self._gradual_time = t
        self._speed_gradual_max = True

    def speed_instant_max(self):
        '''set arms velocity to the maximum value immediately, instead of gradually increasing.'''
        self.arm_velocity_limit = 30.0

    def _Is_weak_motor(self, motor_index):
        weak_motors = [
            R1_A7_JointIndex.kLeftAnklePitch.value,
            R1_A7_JointIndex.kRightAnklePitch.value,
            # Left arm
            R1_A7_JointIndex.kLeftShoulderPitch.value,
            R1_A7_JointIndex.kLeftShoulderRoll.value,
            R1_A7_JointIndex.kLeftShoulderYaw.value,
            R1_A7_JointIndex.kLeftElbow.value,
            # Right arm
            R1_A7_JointIndex.kRightShoulderPitch.value,
            R1_A7_JointIndex.kRightShoulderRoll.value,
            R1_A7_JointIndex.kRightShoulderYaw.value,
            R1_A7_JointIndex.kRightElbow.value,
        ]
        return motor_index.value in weak_motors

    def _Is_wrist_motor(self, motor_index):
        wrist_motors = [
            R1_A7_JointIndex.kLeftWristRoll.value,
            R1_A7_JointIndex.kLeftWristPitch.value,
            R1_A7_JointIndex.kLeftWristyaw.value,
            R1_A7_JointIndex.kRightWristRoll.value,
            R1_A7_JointIndex.kRightWristPitch.value,
            R1_A7_JointIndex.kRightWristYaw.value,
        ]
        return motor_index.value in wrist_motors

class R1_A7_JointArmIndex(IntEnum):
    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28

class R1_A7_JointHeadIndex(IntEnum):
    kHeadPitch = 29
    kHeadYaw = 30

class R1_A7_JointIndex(IntEnum):
    # Left leg
    kLeftHipPitch = 0
    kLeftHipRoll = 1
    kLeftHipYaw = 2
    kLeftKnee = 3
    kLeftAnklePitch = 4
    kLeftAnkleRoll = 5

    # Right leg
    kRightHipPitch = 6
    kRightHipRoll = 7
    kRightHipYaw = 8
    kRightKnee = 9
    kRightAnklePitch = 10
    kRightAnkleRoll = 11

    kWaistYaw = 12
    kWaistRoll = 13
    kWaistPitch = 14

    # Left arm
    kLeftShoulderPitch = 15
    kLeftShoulderRoll = 16
    kLeftShoulderYaw = 17
    kLeftElbow = 18
    kLeftWristRoll = 19
    kLeftWristPitch = 20
    kLeftWristyaw = 21

    # Right arm
    kRightShoulderPitch = 22
    kRightShoulderRoll = 23
    kRightShoulderYaw = 24
    kRightElbow = 25
    kRightWristRoll = 26
    kRightWristPitch = 27
    kRightWristYaw = 28

    # Head
    kHeadPitch = 29
    kHeadYaw = 30

    # not used
    kNotUsedJoint0 = 31
    kNotUsedJoint1 = 32
    kNotUsedJoint2 = 33
    kNotUsedJoint3 = 34

if __name__ == "__main__":
    from robot_arm_ik import G1_29_ArmIK, G1_23_ArmIK, H1_2_ArmIK, H1_ArmIK, H2_ArmIK
    import pinocchio as pin

    ChannelFactoryInitialize(1) # 0 for real robot, 1 for simulation

    # arm_ik = G1_29_ArmIK(Unit_Test = True, Visualization = False)
    # arm = G1_29_ArmController(simulation_mode=True)
    # arm_ik = G1_23_ArmIK(Unit_Test = True, Visualization = False)
    # arm = G1_23_ArmController()
    # arm_ik = H1_2_ArmIK(Unit_Test = True, Visualization = False)
    # arm = H1_2_ArmController()
    # arm_ik = H1_ArmIK(Unit_Test = True, Visualization = True)
    # arm = H1_ArmController()
    arm_ik = H2_ArmIK(Unit_Test = True, Visualization = False)
    arm = H2_ArmController()


    # initial positon
    L_tf_target = pin.SE3(
        pin.Quaternion(1, 0, 0, 0),
        np.array([0.25, +0.25, 0.1]),
    )

    R_tf_target = pin.SE3(
        pin.Quaternion(1, 0, 0, 0),
        np.array([0.25, -0.25, 0.1]),
    )

    rotation_speed = 0.005  # Rotation speed in radians per iteration

    user_input = input("Please enter the start signal (enter 's' to start the subsequent program): \n")
    if user_input.lower() == 's':
        step = 0
        arm.speed_gradual_max()
        while True:
            if step <= 120:
                angle = rotation_speed * step
                L_quat = pin.Quaternion(np.cos(angle / 2), 0, np.sin(angle / 2), 0)  # y axis
                R_quat = pin.Quaternion(np.cos(angle / 2), 0, 0, np.sin(angle / 2))  # z axis

                L_tf_target.translation += np.array([0.001,  0.001, 0.001])
                R_tf_target.translation += np.array([0.001, -0.001, 0.001])
            else:
                angle = rotation_speed * (240 - step)
                L_quat = pin.Quaternion(np.cos(angle / 2), 0, np.sin(angle / 2), 0)  # y axis
                R_quat = pin.Quaternion(np.cos(angle / 2), 0, 0, np.sin(angle / 2))  # z axis

                L_tf_target.translation -= np.array([0.001,  0.001, 0.001])
                R_tf_target.translation -= np.array([0.001, -0.001, 0.001])

            L_tf_target.rotation = L_quat.toRotationMatrix()
            R_tf_target.rotation = R_quat.toRotationMatrix()

            current_lr_arm_q  = arm.get_current_dual_arm_q()
            current_lr_arm_dq = arm.get_current_dual_arm_dq()

            sol_q, sol_tauff = arm_ik.solve_ik(L_tf_target.homogeneous, R_tf_target.homogeneous, current_lr_arm_q, current_lr_arm_dq)

            arm.ctrl_dual_arm(sol_q, sol_tauff)

            step += 1
            if step > 240:
                step = 0
            time.sleep(0.01)
