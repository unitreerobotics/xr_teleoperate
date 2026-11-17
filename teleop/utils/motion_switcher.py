# for motion switcher
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
# for loco client
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
import time

# MotionSwitcher used to switch mode between debug mode and ai mode
class MotionSwitcher:
    def __init__(self):
        self.msc = MotionSwitcherClient()
        self.msc.SetTimeout(1.0)
        self.msc.Init()

    def Enter_Debug_Mode(self):
        try:
            status, result = self.msc.CheckMode()
            while result['name']:
                self.msc.ReleaseMode()
                status, result = self.msc.CheckMode()
                time.sleep(1)
            return status, result
        except Exception as e:
            return None, None
    
    def Exit_Debug_Mode(self):
        try:
            status, result = self.msc.SelectMode(nameOrAlias='ai')
            return status, result
        except Exception as e:
            return None, None

class LocoClientWrapper:
    def __init__(self):
        self.client = LocoClient()
        self.client.SetTimeout(1.0)     # generous timeout for the FSM handshake
        self.client.Init()
        self._enter_control_mode()      # G1 sw 1.5.3: reach the walkable state via 1 -> 4 -> 501 (see below)
        self.client.SetTimeout(0.0001)  # fast, non-blocking for the high-rate Move loop

    def _enter_control_mode(self):
        """Bring the G1 into its walkable 'main operation control' state on sw 1.5.3.

        The SDK's Start() sets FSM 500, but this firmware ignores it: from the R2+A "Running" mode
        (FSM 802), SetFsmId(500) returns success yet the robot never leaves 802. Verified on-robot,
        the walkable state on 1.5.3 is FSM 501, reached via: damp(1) -> stand(4) -> main-control(501).
        SetVelocity/Move only take effect once in 501. (Override the target with G1_CTRL_FSM if a
        future firmware changes it.)

        The stand-up (4) is a PHYSICAL motion that takes several seconds; SetFsmId(501) is silently
        ignored until it finishes (the FSM sticks at 4). So we wait, then RETRY 501 until GetFsmId
        confirms we actually reached it.
        """
        import os
        target = int(os.environ.get("G1_CTRL_FSM", "501"))
        self.client.SetFsmId(1)          # damp
        time.sleep(1.0)
        self.client.SetFsmId(4)          # stand up — physical motion, takes a few seconds
        time.sleep(5.0)
        fid = None
        for attempt in range(1, 13):     # retry 501 until it takes (stand-up timing varies)
            self.client.SetFsmId(target)
            time.sleep(1.0)
            _, fid = self.client.GetFsmId()
            if fid == target:
                break
        if fid == target:
            print(f"[LocoClientWrapper] control mode reached: FSM id = {target} (attempt {attempt})")
        else:
            print(f"[LocoClientWrapper] WARNING: FSM id = {fid}, wanted {target} after {attempt} tries "
                  f"— robot may not have finished standing; increase the stand wait.")

    def Enter_Damp_Mode(self):
        self.client.Damp()
    
    def Move(self, vx, vy, vyaw):
        self.client.Move(vx, vy, vyaw, continous_move=False)

if __name__ == '__main__':
    ChannelFactoryInitialize(1) # 0 for real robot, 1 for simulation
    ms = MotionSwitcher()
    status, result = ms.Enter_Debug_Mode()
    print("Enter debug mode:", status, result)
    time.sleep(5)
    status, result = ms.Exit_Debug_Mode()
    print("Exit debug mode:", status, result)
    time.sleep(2)
