#!/usr/bin/env python3
"""
Hand-mode walking for xr_teleoperate (G1, --input-mode=hand --motion).

In controller mode the operator walks with the thumbsticks and the legs follow
`loco_wrapper.Move(vx, vy, vyaw)` (see teleop_hand_and_arm.py). In HAND mode there
are no thumbsticks, so this module reproduces the same three axes from ARM DISPLACEMENT
and lets the operator flip between manipulating and walking with a head gesture:

    * HAND-TRACK mode (default): arms IK-track, fingers grasp normally, legs held (Move 0,0,0).
    * WALK mode:                 arms are FROZEN (they become the joystick); displacing an
                                 arm from the pose captured on entry drives locomotion, with
                                 the exact same axis mapping as the thumbsticks:
                                     left  arm forward/back -> vx   (walk forward/back)
                                     left  arm left/right    -> vy   (strafe)
                                     right arm left/right    -> vyaw (turn)

    * A DOUBLE downward head-nod toggles between the two modes.

Wrist/head poses are in the arm-IK target frame (robot basis: x=forward, y=left, z=up),
so displacement axes map straight onto (vx, vy, vyaw).

Everything is env-tunable (no code edits to calibrate on the gantry) and every default is
conservative. Set WALK_DEBUG=1 / NOD_DEBUG=1 to print the live signals while calibrating.

Standalone sanity check (no robot, no XR):
    python -m teleop.utils.hand_walk        # feeds synthetic nods through NodDetector
"""
import os
import math

import numpy as np


def _f(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _i(name, default):
    try:
        return int(float(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return int(default)


_WALK_DEBUG = bool(os.environ.get("WALK_DEBUG"))
_NOD_DEBUG = bool(os.environ.get("NOD_DEBUG"))


# ------------------------------------------------------------------------------------
#  Head-nod detector: a DOUBLE downward pitch dip within a time window fires a toggle.
# ------------------------------------------------------------------------------------
class NodDetector:
    """Frame-agnostic double-nod detector.

    The "pitch signal" is one entry of the head rotation matrix (default R[1,2] = the
    world-vertical (OpenXR Y-up) component of the head's fore-aft axis). Nodding the head
    down tilts that axis and moves the signal; we track it against a slow EMA baseline and
    count *downward* dips (deviation past `enter_thresh`, released below enter_thresh*exit_frac
    with hysteresis). `needed` dips inside `window_s` -> fire (then a refractory lockout so the
    same gesture can't double-fire). Left/right head *shake* (yaw) doesn't move a vertical
    matrix entry, so ordinary looking-around won't trigger it.

    All parameters are env-tunable; if the sign or the chosen matrix cell is wrong for your
    headset frame, set NOD_SIGN / NOD_ROW / NOD_COL (watch NOD_DEBUG output to pick them).
    """

    def __init__(self, needed=None, window_s=None, enter_thresh=None, exit_frac=None,
                 baseline_tau_s=None, refractory_s=None, sign=None, row=None, col=None):
        self.needed = _i("NOD_COUNT", 2) if needed is None else needed
        self.window_s = _f("NOD_WINDOW_S", 3.0) if window_s is None else window_s
        self.enter_thresh = _f("NOD_ENTER", 0.12) if enter_thresh is None else enter_thresh
        self.exit_frac = _f("NOD_EXIT_FRAC", 0.5) if exit_frac is None else exit_frac
        self.baseline_tau_s = _f("NOD_BASELINE_TAU", 1.0) if baseline_tau_s is None else baseline_tau_s
        self.refractory_s = _f("NOD_REFRACTORY_S", 1.0) if refractory_s is None else refractory_s
        self.sign = _f("NOD_SIGN", 1.0) if sign is None else sign
        self.row = _i("NOD_ROW", 1) if row is None else row   # OpenXR Y-up: vertical = row 1
        self.col = _i("NOD_COL", 2) if col is None else col   # fore-aft axis = col 2

        self.baseline = None
        self.in_dip = False
        self.dips = []           # timestamps of completed downward dips
        self.last_fire = -1e9
        self.last_now = None

    def signal_from_head(self, head_pose):
        """Extract the pitch signal from a 4x4 head pose (robot basis, z-up)."""
        R = np.asarray(head_pose, dtype=np.float64).reshape(4, 4)[:3, :3]
        return self.sign * float(R[self.row, self.col])

    def update(self, signal, now):
        """Feed the current pitch `signal` (float) at time `now` (seconds). Returns True once
        on the frame a double-nod completes."""
        if self.baseline is None:
            self.baseline = signal
            self.last_now = now
            return False

        dt = max(1e-3, now - (self.last_now if self.last_now is not None else now))
        self.last_now = now

        # slow EMA baseline so a quick nod shows up as a transient deviation
        alpha = dt / (self.baseline_tau_s + dt)
        self.baseline += alpha * (signal - self.baseline)

        # downward deviation (nodding the head down drives this positive with the default sign)
        deviation = self.baseline - signal

        # prune old dips
        self.dips = [t for t in self.dips if now - t <= self.window_s]

        fired = False
        if not self.in_dip:
            if deviation > self.enter_thresh:
                self.in_dip = True
        else:
            if deviation < self.enter_thresh * self.exit_frac:
                self.in_dip = False
                self.dips.append(now)
                self.dips = [t for t in self.dips if now - t <= self.window_s]
                if len(self.dips) >= self.needed and (now - self.last_fire) > self.refractory_s:
                    self.last_fire = now
                    self.dips = []
                    fired = True

        if _NOD_DEBUG:
            print(f"[nod] sig={signal:+.3f} base={self.baseline:+.3f} dev={deviation:+.3f} "
                  f"dip={int(self.in_dip)} dips={len(self.dips)} fired={int(fired)}", flush=True)
        return fired


# ------------------------------------------------------------------------------------
#  Arm-displacement -> locomotion velocity
# ------------------------------------------------------------------------------------
def _deadzoned(disp, gain, sign, deadzone, vmax):
    """Map a signed displacement (meters) to a clamped velocity with a deadzone."""
    if abs(disp) < deadzone:
        return 0.0
    disp = disp - math.copysign(deadzone, disp)   # continuous past the deadzone edge
    v = sign * gain * disp
    return float(max(-vmax, min(vmax, v)))


def _xyz(pose):
    return np.asarray(pose, dtype=np.float64).reshape(4, 4)[:3, 3]


class HandWalkController:
    """Owns the hand-mode walk/hand-track state machine.

    Call `update(head_pose, left_wrist_pose, right_wrist_pose, now)` once per loop.
    Returns a dict:
        walk_mode : bool   -- True while steering (arms should be frozen by the caller)
        toggled   : bool   -- True on the frame the nod flipped the mode
        vx,vy,vyaw: float   -- feed straight into loco_wrapper.Move(vx, vy, vyaw)
    """

    def __init__(self):
        self.vmax = _f("WALK_VMAX", 0.3)
        self.deadzone = _f("WALK_DEADZONE_M", 0.05)
        self.gain_fwd = _f("WALK_GAIN_FWD", 1.5)
        self.gain_strafe = _f("WALK_GAIN_STRAFE", 1.5)
        self.gain_turn = _f("WALK_GAIN_TURN", 2.0)
        self.sign_fwd = _f("WALK_SIGN_FWD", 1.0)
        self.sign_strafe = _f("WALK_SIGN_STRAFE", 1.0)
        self.sign_turn = _f("WALK_SIGN_TURN", 1.0)

        self.nod = NodDetector()
        self.walk_mode = False
        self.neutral_l = None     # left wrist xyz captured on entering walk
        self.neutral_r = None     # right wrist xyz captured on entering walk
        self._dbg = 0

    def update(self, head_pose, left_wrist_pose, right_wrist_pose, now):
        toggled = self.nod.update(self.nod.signal_from_head(head_pose), now)
        if toggled:
            self.walk_mode = not self.walk_mode
            if self.walk_mode:
                # capture the current arm pose as the joystick center
                self.neutral_l = _xyz(left_wrist_pose).copy()
                self.neutral_r = _xyz(right_wrist_pose).copy()
            else:
                self.neutral_l = self.neutral_r = None

        vx = vy = vyaw = 0.0
        if self.walk_mode and self.neutral_l is not None and self.neutral_r is not None:
            lp = _xyz(left_wrist_pose)
            rp = _xyz(right_wrist_pose)
            l_dx = lp[0] - self.neutral_l[0]   # left arm forward/back  (robot x)
            l_dy = lp[1] - self.neutral_l[1]   # left arm left/right    (robot y)
            r_dy = rp[1] - self.neutral_r[1]   # right arm left/right   (robot y)
            vx = _deadzoned(l_dx, self.gain_fwd, self.sign_fwd, self.deadzone, self.vmax)
            vy = _deadzoned(l_dy, self.gain_strafe, self.sign_strafe, self.deadzone, self.vmax)
            vyaw = _deadzoned(r_dy, self.gain_turn, self.sign_turn, self.deadzone, self.vmax)
            if _WALK_DEBUG:
                self._dbg += 1
                if self._dbg % 10 == 0:
                    print(f"[walk] Ldisp=[{l_dx:+.3f},{l_dy:+.3f}] Rdisp_y={r_dy:+.3f} "
                          f"-> vx={vx:+.2f} vy={vy:+.2f} vyaw={vyaw:+.2f}", flush=True)

        return {"walk_mode": self.walk_mode, "toggled": toggled, "vx": vx, "vy": vy, "vyaw": vyaw}


def _selftest():
    """Feed a synthetic pitch signal through NodDetector: two nods, gap, then two more."""
    det = NodDetector(needed=2, window_s=1.5, refractory_s=0.8)
    t = 0.0
    dt = 1.0 / 60.0
    fires = []

    def feed(sig, secs):
        nonlocal t
        n = int(secs / dt)
        for _ in range(n):
            if det.update(sig, t):
                fires.append(round(t, 2))
            t += dt

    baseline = 1.0            # signal rests near R[2,2]=1 (head level, forward ~horizontal)
    feed(baseline, 1.5)       # settle baseline
    # nod 1: dip down and back
    feed(baseline - 0.30, 0.15); feed(baseline, 0.15)
    # nod 2 (within window) -> should FIRE once
    feed(baseline - 0.30, 0.15); feed(baseline, 0.5)
    # single stray nod -> should NOT fire
    feed(baseline - 0.30, 0.15); feed(baseline, 1.2)
    # two more nods -> FIRE again
    feed(baseline - 0.30, 0.15); feed(baseline, 0.15)
    feed(baseline - 0.30, 0.15); feed(baseline, 0.5)

    print(f"fires at t={fires}  (expected exactly 2 toggle events)")
    assert len(fires) == 2, f"expected 2 fires, got {len(fires)}"
    print("NodDetector self-test PASSED")


if __name__ == "__main__":
    _selftest()
