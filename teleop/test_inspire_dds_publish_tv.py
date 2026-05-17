# test_inspire_dds_publish_tv.py
import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from inspire_sdkpy import inspire_dds, inspire_hand_defaut

if __name__ == "__main__":
    # 和 inspire_hand_ws 里的 dds_publish.py 保持完全一致
    ChannelFactoryInitialize(0)  # 如果官方 dds_publish 带第二个参数，这里也要带同样的

    pub_r = ChannelPublisher("rt/inspire_hand/ctrl/r", inspire_dds.inspire_hand_ctrl)
    pub_l = ChannelPublisher("rt/inspire_hand/ctrl/l", inspire_dds.inspire_hand_ctrl)
    pub_r.Init()
    pub_l.Init()

    cmd = inspire_hand_defaut.get_inspire_hand_ctrl()

    print(">>> Send open command")
    cmd.angle_set = [0, 0, 0, 0, 1000, 1000]
    cmd.mode = 0b0001
    pub_l.Write(cmd)
    pub_r.Write(cmd)
    time.sleep(2.0)

    print(">>> Send close command")
    cmd.angle_set = [0, 0, 0, 0, 0, 1000]
    cmd.mode = 0b0001
    pub_l.Write(cmd)
    pub_r.Write(cmd)

    print("Done. Wait 3s...")
    time.sleep(3.0)
