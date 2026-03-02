from typing import Optional
import time
import numpy as np

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import HandCmd_, HandState_
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__HandCmd_

from teleop.robot_control.robot_hand_unitree import (
    Dex3_1_Controller,
    Dex3_1_Left_JointIndex,
    Dex3_1_Right_JointIndex,
)

DEX3_GRAB_POSE_RIGHT = np.array([-0.0, -1.0, -1.70, 1.55, 1.75, 1.55, 1.75], dtype=np.float64)
DEX3_GRAB_POSE_LEFT = np.array([0.0, 1.0, 1.70, -1.55, -1.75, -1.55, -1.75], dtype=np.float64)
DEX3_OPEN_POSE = np.zeros(7, dtype=np.float64)


class Dex3HandIO:
    def __init__(
        self,
        kp: float = 1.5,
        kd: float = 0.2,
        tare_delay: float = 0.6,
        pressure_scale: float = 100.0,
        press_base_n: int = 30,
    ):
        self.right_pub = ChannelPublisher("rt/dex3/right/cmd", HandCmd_)
        self.right_pub.Init()
        self.left_pub = ChannelPublisher("rt/dex3/left/cmd", HandCmd_)
        self.left_pub.Init()
        self.right_state_sub = ChannelSubscriber("rt/dex3/right/state", HandState_)
        self.right_state_sub.Init()
        self.left_state_sub = ChannelSubscriber("rt/dex3/left/state", HandState_)
        self.left_state_sub.Init()

        self.tare_delay = tare_delay
        self.pressure_scale = pressure_scale
        self.press_base_n = press_base_n

        self.right_tau = np.zeros(7, dtype=np.float64)
        self.left_tau = np.zeros(7, dtype=np.float64)
        self.right_q_state = np.zeros(7, dtype=np.float64)
        self.left_q_state = np.zeros(7, dtype=np.float64)
        self.right_press = np.zeros(9, dtype=np.float64)
        self.left_press = np.zeros(9, dtype=np.float64)
        self.right_press_base = np.zeros(9, dtype=np.float64)
        self.left_press_base = np.zeros(9, dtype=np.float64)
        self.right_press_corr = np.zeros(9, dtype=np.float64)
        self.left_press_corr = np.zeros(9, dtype=np.float64)
        self.press_base_ready = False
        self.press_base_samples = 0

        self.right_release_time: Optional[float] = None
        self.left_release_time: Optional[float] = None
        self._prev_right_closed = False
        self._prev_left_closed = False
        self.right_hold_logged = [False] * 7
        self.left_hold_logged = [False] * 7
        self.right_ramped_target = np.zeros(7, dtype=np.float64)
        self.left_ramped_target = np.zeros(7, dtype=np.float64)

        # SmartGrip parameters from teleop_hand_and_arm_grab.py
        self.kp_move = kp
        self.kd_move = kd
        self.kp_hold = 0.8
        self.kd_hold = 0.2
        self.pressure_threshold = 0.20
        self.pressure_threshold_base = 0.05
        self.pressure_threshold_exit = 0.15
        self.pressure_threshold_base_exit = 0.03
        self.torque_threshold_high = 200000.0
        self.squeeze_offset = 0.08
        self.ramp_factor = 0.20
        self.thumb_completion_threshold = 0.05

        self.right_msg = unitree_hg_msg_dds__HandCmd_()
        self.left_msg = unitree_hg_msg_dds__HandCmd_()

        for jid in Dex3_1_Right_JointIndex:
            ris = Dex3_1_Controller._RIS_Mode(id=jid, status=0x01)
            self.right_msg.motor_cmd[jid].mode = ris._mode_to_uint8()
            self.right_msg.motor_cmd[jid].kp = kp
            self.right_msg.motor_cmd[jid].kd = kd
            self.right_msg.motor_cmd[jid].tau = 0.0
            self.right_msg.motor_cmd[jid].dq = 0.0

        for jid in Dex3_1_Left_JointIndex:
            ris = Dex3_1_Controller._RIS_Mode(id=jid, status=0x01)
            self.left_msg.motor_cmd[jid].mode = ris._mode_to_uint8()
            self.left_msg.motor_cmd[jid].kp = kp
            self.left_msg.motor_cmd[jid].kd = kd
            self.left_msg.motor_cmd[jid].tau = 0.0
            self.left_msg.motor_cmd[jid].dq = 0.0

    def publish_targets(self, left_q: np.ndarray, right_q: np.ndarray) -> np.ndarray:
        for i, jid in enumerate(Dex3_1_Left_JointIndex):
            self.left_msg.motor_cmd[jid].q = float(left_q[i])
        for i, jid in enumerate(Dex3_1_Right_JointIndex):
            self.right_msg.motor_cmd[jid].q = float(right_q[i])

        self.right_pub.Write(self.right_msg)
        self.left_pub.Write(self.left_msg)
        return np.concatenate([left_q, right_q], axis=0)

    def _update_release_edges(self, right_closed: bool, left_closed: bool, now: float) -> None:
        if self._prev_right_closed and not right_closed:
            self.right_release_time = now
        if self._prev_left_closed and not left_closed:
            self.left_release_time = now
        self._prev_right_closed = right_closed
        self._prev_left_closed = left_closed

    def _update_dex3_feedback(self, right_closed: bool, left_closed: bool) -> None:
        now = time.time()
        self._update_release_edges(right_closed=right_closed, left_closed=left_closed, now=now)

        try:
            rmsg = self.right_state_sub.Read()
            lmsg = self.left_state_sub.Read()

            if rmsg is not None:
                for i, jid in enumerate(Dex3_1_Right_JointIndex):
                    self.right_tau[i] = float(rmsg.motor_state[jid].tau_est)
                    self.right_q_state[i] = float(rmsg.motor_state[jid].q)
                m = min(9, len(rmsg.press_sensor_state))
                for si in range(m):
                    pads = rmsg.press_sensor_state[si].pressure
                    self.right_press[si] = float(sum(pads) / len(pads)) if len(pads) > 0 else 0.0

            if lmsg is not None:
                for i, jid in enumerate(Dex3_1_Left_JointIndex):
                    self.left_tau[i] = float(lmsg.motor_state[jid].tau_est)
                    self.left_q_state[i] = float(lmsg.motor_state[jid].q)
                m = min(9, len(lmsg.press_sensor_state))
                for si in range(m):
                    pads = lmsg.press_sensor_state[si].pressure
                    self.left_press[si] = float(sum(pads) / len(pads)) if len(pads) > 0 else 0.0

            if not self.press_base_ready:
                self.right_press_base += self.right_press
                self.left_press_base += self.left_press
                self.press_base_samples += 1
                if self.press_base_samples >= self.press_base_n:
                    self.right_press_base /= self.press_base_samples
                    self.left_press_base /= self.press_base_samples
                    self.press_base_ready = True
        except Exception:
            pass

        if self.right_release_time is not None and (now - self.right_release_time) >= self.tare_delay:
            self.right_press_base = self.right_press.copy()
            self.right_release_time = None
        if self.left_release_time is not None and (now - self.left_release_time) >= self.tare_delay:
            self.left_press_base = self.left_press.copy()
            self.left_release_time = None

        if self.press_base_ready:
            self.right_press_corr = np.maximum(0.0, (self.right_press - self.right_press_base) / self.pressure_scale)
            self.left_press_corr = np.maximum(0.0, (self.left_press - self.left_press_base) / self.pressure_scale)
        else:
            self.right_press_corr = self.right_press / self.pressure_scale
            self.left_press_corr = self.left_press / self.pressure_scale

    def get_feedback(self) -> dict:
        return {
            "right_tau": self.right_tau.copy(),
            "left_tau": self.left_tau.copy(),
            "right_q_state": self.right_q_state.copy(),
            "left_q_state": self.left_q_state.copy(),
            "right_press": self.right_press.copy(),
            "left_press": self.left_press.copy(),
            "right_press_base": self.right_press_base.copy(),
            "left_press_base": self.left_press_base.copy(),
            "right_press_corr": self.right_press_corr.copy(),
            "left_press_corr": self.left_press_corr.copy(),
            "press_base_ready": self.press_base_ready,
        }

    def _build_open_side_cmd(self, side: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        q = DEX3_OPEN_POSE.copy()
        kp = np.full(7, self.kp_move, dtype=np.float64)
        kd = np.full(7, self.kd_move, dtype=np.float64)
        if side == "right":
            self.right_ramped_target[:] = q
            self.right_hold_logged = [False] * 7
        else:
            self.left_ramped_target[:] = q
            self.left_hold_logged = [False] * 7
        return q, kp, kd

    def _build_close_side_cmd(self, side: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if side == "right":
            target_pose = DEX3_GRAB_POSE_RIGHT
            current_q = self.right_q_state
            tau = self.right_tau
            hold_logged = self.right_hold_logged
            ramped = self.right_ramped_target
            thumb_tip = self.right_press_corr[1]
            thumb_base = self.right_press_corr[0]
            index_tip = self.right_press_corr[3]
            index_base = self.right_press_corr[2]
            middle_tip = self.right_press_corr[5]
            middle_base = self.right_press_corr[4]
        else:
            target_pose = DEX3_GRAB_POSE_LEFT
            current_q = self.left_q_state
            tau = self.left_tau
            hold_logged = self.left_hold_logged
            ramped = self.left_ramped_target
            thumb_tip = self.left_press_corr[1]
            thumb_base = self.left_press_corr[0]
            index_tip = self.left_press_corr[5]
            index_base = self.left_press_corr[4]
            middle_tip = self.left_press_corr[3]
            middle_base = self.left_press_corr[2]

        # Thumb leads closure
        final_thumb_target = target_pose[0]
        ramped[0] = ramped[0] + (final_thumb_target - ramped[0]) * self.ramp_factor
        thumb_is_done = abs(ramped[0] - final_thumb_target) < self.thumb_completion_threshold

        q = np.zeros(7, dtype=np.float64)
        kp = np.zeros(7, dtype=np.float64)
        kd = np.zeros(7, dtype=np.float64)

        for i in range(7):
            final_target = target_pose[i]
            if hold_logged[i]:
                thresh_main = self.pressure_threshold_exit
                thresh_base = self.pressure_threshold_base_exit
            else:
                thresh_main = self.pressure_threshold
                thresh_base = self.pressure_threshold_base

            is_high_torque = abs(tau[i]) > self.torque_threshold_high
            should_hold = False
            if i == 1:
                should_hold = (thumb_base > thresh_main or thumb_tip > thresh_main or is_high_torque)
            elif i == 2:
                should_hold = (thumb_tip > thresh_main or is_high_torque)
            elif i == 3:
                should_hold = (middle_base > thresh_base or middle_tip > thresh_main or is_high_torque)
            elif i == 4:
                should_hold = (middle_tip > thresh_main or is_high_torque)
            elif i == 5:
                should_hold = (index_base > thresh_base or index_tip > thresh_main or is_high_torque)
            elif i == 6:
                should_hold = (index_tip > thresh_main or is_high_torque)

            if should_hold:
                if not hold_logged[i]:
                    direction = 1.0 if final_target > current_q[i] else -1.0
                    ramped[i] = current_q[i] + (self.squeeze_offset * direction)
                    hold_logged[i] = True
                q[i] = ramped[i]
                kp[i] = self.kp_hold
                kd[i] = self.kd_hold
            else:
                if i == 0 or thumb_is_done:
                    ramped[i] = ramped[i] + (final_target - ramped[i]) * self.ramp_factor
                q[i] = ramped[i]
                kp[i] = self.kp_move
                kd[i] = self.kd_move
                hold_logged[i] = False

        return q, kp, kd

    def hand_IO_ctrl(self, action: str, side: str = "both", publish: bool = True) -> np.ndarray:
        action_l = action.lower().strip()
        side_l = side.lower().strip()
        if action_l not in ("open", "close"):
            raise ValueError(f"Invalid action '{action}'. Expected 'open' or 'close'.")
        if side_l not in ("left", "right", "both"):
            raise ValueError(f"Invalid side '{side}'. Expected 'left', 'right', or 'both'.")

        left_closed = action_l == "close" and side_l in ("left", "both")
        right_closed = action_l == "close" and side_l in ("right", "both")

        self._update_dex3_feedback(right_closed=right_closed, left_closed=left_closed)

        if left_closed:
            left_q, left_kp, left_kd = self._build_close_side_cmd("left")
        else:
            left_q, left_kp, left_kd = self._build_open_side_cmd("left")

        if right_closed:
            right_q, right_kp, right_kd = self._build_close_side_cmd("right")
        else:
            right_q, right_kp, right_kd = self._build_open_side_cmd("right")

        for i, jid in enumerate(Dex3_1_Left_JointIndex):
            self.left_msg.motor_cmd[jid].kp = float(left_kp[i])
            self.left_msg.motor_cmd[jid].kd = float(left_kd[i])
        for i, jid in enumerate(Dex3_1_Right_JointIndex):
            self.right_msg.motor_cmd[jid].kp = float(right_kp[i])
            self.right_msg.motor_cmd[jid].kd = float(right_kd[i])

        q14 = np.concatenate([left_q, right_q], axis=0)
        if publish:
            return self.publish_targets(left_q, right_q)
        return q14

_DEFAULT_IO: Optional[Dex3HandIO] = None


def get_hand_io_controller() -> Dex3HandIO:
    global _DEFAULT_IO
    if _DEFAULT_IO is None:
        _DEFAULT_IO = Dex3HandIO()
    return _DEFAULT_IO


def hand_IO_ctrl(action: str, side: str = "both", publish: bool = True, controller: Optional[Dex3HandIO] = None) -> np.ndarray:
    ctrl = controller or get_hand_io_controller()
    return ctrl.hand_IO_ctrl(action=action, side=side, publish=publish)


if __name__ == "__main__":
    io = get_hand_io_controller()
    action = "open"
    try:
        while True:
            hand_IO_ctrl(action, controller=io)
            print(f"[hand_IO_control] sent action: {action}")
            time.sleep(3.0)
            action = "close" if action == "open" else "open"
    except KeyboardInterrupt:
        print("\n[hand_IO_control] stopped.")
