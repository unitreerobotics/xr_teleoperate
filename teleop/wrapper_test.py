#!/usr/bin/env python3
"""
Quick isolated test of the FIXED LocoClientWrapper (damp(1) -> stand(4) -> 501 on G1 sw 1.5.3).
Confirms the wrapper's automated FSM sequence + timing reach the walkable state and that Move walks,
without bringing up the full teleop (no televuer / arms / cameras).

SAFETY: robot on the gantry / supported, e-stop ready (it damps then stands at startup).
RUN (tv env):  python wrapper_test.py <interface>     e.g. python wrapper_test.py enxf8e43b46612e
"""
import os
import sys
import time

# make `teleop.utils.motion_switcher` importable (xr_teleoperate repo root on sys.path)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from teleop.utils.motion_switcher import LocoClientWrapper

iface = sys.argv[1] if len(sys.argv) > 1 else "enxf8e43b46612e"
print(f"[wrapper_test] iface={iface} — building LocoClientWrapper (runs damp -> stand -> 501)...")
ChannelFactoryInitialize(0, iface)          # 0 = real robot
w = LocoClientWrapper()                       # should print 'control mode: FSM id = 501'

input("[wrapper_test] FSM id = 501 above? ENTER to Move forward ~2s (GANTRY!): ")
for _ in range(20):
    w.Move(0.1, 0.0, 0.0)
    time.sleep(0.1)
w.Move(0.0, 0.0, 0.0)
print("[wrapper_test] done — if the feet stepped, the locomotion fix works end-to-end via the wrapper.")
