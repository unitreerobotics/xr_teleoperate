#!/usr/bin/env python3
"""
Interactive G1 high-level FSM explorer — find the transition path from FSM 802 (the R2+A
"Running" mode) to a walkable state (main operation control / FSM 500) on sw 1.5.3.

SAFETY: robot on the gantry / supported, e-stop ready. Some FSM ids cause motion or make the
robot limp (0 = zero-torque, 1 = damp). Try gentle transitions and WATCH the robot each time.

RUN (tv env):  python fsm_explore.py <interface>       e.g. python fsm_explore.py enxf8e43b46612e

At the  fsm>  prompt:
   <number>   SetFsmId(number), then print the resulting FSM id
   v          send vx=0.1 for ~2s  (does the CURRENT FSM actually walk? watch the feet) then stop
   g          just GetFsmId
   q          quit (damps first for safety)

Reference ids: 0 zero-torque | 1 damp | 3 sit | 500 main-control(walk) | 702 lie2stand | 706 squat2stand
Suggested probes from 802:   1  ->g->  500 ->g-> v     and     706 ->g-> v
"""
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient


def main():
    iface = sys.argv[1] if len(sys.argv) > 1 else "enxf8e43b46612e"
    ChannelFactoryInitialize(0, iface)
    c = LocoClient()
    c.SetTimeout(3.0)
    c.Init()

    def show():
        code, fid = c.GetFsmId()
        print(f"     -> FSM id = {fid}   (GetFsmId code {code})")
        return fid

    print("G1 FSM explorer.  commands: <number>=SetFsmId | v=test-walk 2s | g=GetFsmId | q=quit")
    print("ids: 0 zero-torque | 1 damp | 3 sit | 500 main-control(walk) | 702 lie2stand | 706 squat2stand")
    show()
    while True:
        try:
            cmd = input("fsm> ").strip().lower()
        except EOFError:
            break
        if cmd == "q":
            c.SetFsmId(1)
            print("damped. bye")
            break
        elif cmd == "g":
            show()
        elif cmd == "v":
            print("     sending vx=0.1 for ~2s (watch the feet)...")
            for _ in range(20):
                c.SetVelocity(0.1, 0.0, 0.0, 1.0)
                time.sleep(0.1)
            c.SetVelocity(0.0, 0.0, 0.0)
            print("     stopped")
        elif cmd.lstrip("-").isdigit():
            code = c.SetFsmId(int(cmd))
            print(f"     SetFsmId({cmd}) -> code {code}")
            time.sleep(1.3)
            show()
        else:
            print("     ? enter a number, or v / g / q")


if __name__ == "__main__":
    main()
