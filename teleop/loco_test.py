#!/usr/bin/env python3
"""
Minimal G1 locomotion isolation test (high-level LocoClient) — for debugging the sw-1.5.3
walk issue WITHOUT the full xr_teleoperate stack (no televuer, no arm IK, no cameras).

It prints every FSM state and every return code so we can see EXACTLY where it breaks.

PREREQS
  - Robot ON, on a gantry / clear space, e-stop ready.
  - Robot in the HIGH-LEVEL motion-control mode (the built-in 'sport' service must be RUNNING).
    NOTE: this is the OPPOSITE of the L2+R2 debug mode used for the GEAR-SONIC low-level deploy.
    On fw 1.5.3, R1+X ("Regular") is reportedly rejected — R2+A ("Running") is what engages
    motion-control. Enter that first, then run this. If GetFsmId below returns nonzero, the
    sport service isn't reachable (wrong mode / interface / service name).

RUN (in the tv env, which has unitree_sdk2py):
    conda activate tv
    python loco_test.py <interface>          e.g.  python loco_test.py enxf8e43b46612e
"""
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
from unitree_sdk2py.g1.loco.g1_loco_api import LOCO_SERVICE_NAME


def fsm(c, label):
    code, fid = c.GetFsmId()
    print(f"[loco_test] GetFsmId {label:16s} -> code={code}  fsm_id={fid}")
    return code, fid


def main():
    iface = sys.argv[1] if len(sys.argv) > 1 else "enxf8e43b46612e"
    print(f"[loco_test] interface={iface}   service={LOCO_SERVICE_NAME!r}  (G1 uses 'sport')")
    ChannelFactoryInitialize(0, iface)          # 0 = real robot
    c = LocoClient()
    c.SetTimeout(3.0)                            # generous so we see real errors, not timeouts
    c.Init()
    print("[loco_test] LocoClient Init done\n")

    # 1) Is the sport service responding at all?
    code, fid = fsm(c, "(current)")
    if code != 0:
        print("\n  >>> sport service NOT responding (code != 0).")
        print("      Likely: robot in DEBUG mode (sport off) / wrong interface / service-name mismatch.")
        print("      Fix the robot mode first (motion-control, NOT L2+R2 debug), then re-run.")
        return

    # 2) Try to enter FSM 500 (Start / main operation control)
    code = c.SetFsmId(500)
    print(f"[loco_test] SetFsmId(500)=Start   -> code={code}   (0=ok; nonzero e.g. 3102 = rejected/lease)")
    time.sleep(1.5)
    fsm(c, "(after Start)")

    # 3) Send a small forward velocity — use SetVelocity directly (Move() discards the code)
    ans = input("\n[loco_test] Robot supported/clear? Type 'go' to send vx=0.1 for ~2s (anything else = skip): ")
    if ans.strip().lower() == "go":
        for i in range(20):
            code = c.SetVelocity(0.1, 0.0, 0.0, duration=1.0)
            if i % 5 == 0:
                print(f"[loco_test] SetVelocity(0.1,0,0) -> code={code}")
            time.sleep(0.1)
        c.SetVelocity(0.0, 0.0, 0.0)
        print("[loco_test] velocity zeroed.")

    print("\n[loco_test] done. Report the FSM ids + codes above — that pins down the 1.5.3 failure:")
    print("  - GetFsmId code!=0            -> service/mode problem (not in motion-control).")
    print("  - SetFsmId(500) code!=0       -> FSM transition rejected (Run-mode conflict / lease).")
    print("  - fsm stays != 500 after Start-> robot won't leave its current FSM (e.g. stuck in Run mode).")
    print("  - SetVelocity code!=0         -> velocity command rejected in current FSM.")


if __name__ == "__main__":
    main()
