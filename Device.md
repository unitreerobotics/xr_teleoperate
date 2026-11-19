# 5. 🛠️ Hardware

## 5.1 🎮 Teleoperation Devices

> The following items are required for teleoperation.

<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
  <tr>
    <th style="text-align: center;">Item</th>
    <th style="text-align: center;">Quantity</th>
    <th style="text-align: center;">Specification</th>
    <th style="text-align: center;">Remarks</th>
  </tr>
  <tr>
    <td style="text-align: center;"><b>Unitree General Humanoid Robot G1</b></td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;"><a href="https://www.unitree.com/cn/g1">https://www.unitree.com/cn/g1</a></td>
    <td style="text-align: center;">Developer computing unit version required</td>
  </tr>
  <tr>
    <td style="text-align: center;"><b>XR Device</b></td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;">
      <a href="https://www.apple.com.cn/apple-vision-pro/">apple-vision-pro</a><br />
      <a href="https://www.picoxr.com/products/pico4-ultra-enterprise">pico4-ultra-enterprise</a><br />
      <a href="https://www.meta.com/quest/quest-3">quest-3</a><br />
      <a href="https://www.meta.com/quest/quest-3s/">quest-3s</a><br />
    </td>
    <td style="text-align: center;">
      <a href="https://github.com/unitreerobotics/xr_teleoperate/wiki/XR_Device">Please refer to our WiKi [XR_Device]</a>
    </td>
  </tr>
  <tr>
    <td style="text-align: center;"><b>Router</b></td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;">Recommended: at least WiFi6 support</td>
    <td style="text-align: center;">Required in wired mode; optional in wireless mode.</td>
  </tr>
  <tr>
    <td style="text-align: center;"><b>User Computer</b></td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;">Recommended x86-64 architecture</td>
    <td style="text-align: center;">
      For simulation mode, please follow 
      <a href="https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/requirements.html">NVIDIA official hardware recommendations</a>
      for deployment.
    </td>
  </tr>
  <tr>
    <td style="text-align: center;"><b>Head Camera</b></td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;">
      Monocular camera (built-in Realsense D435i)<br />
      Stereo camera (external mount, see details at chapter 5.2)
    </td>
    <td style="text-align: center;">
      Used for robot head perspective, stereo camera provides more immersion.<br />
      Driven by <a href="https://github.com/unitreerobotics/xr_teleoperate/tree/main/teleop/image_server">image_server</a>
    </td>
  </tr>
  <tr>
    <td style="text-align: center;">USB3.0 Cable</td>
    <td style="text-align: center;">1</td>
    <td style="text-align: center;">
      Type-C double straight connectors, about 0.2m length
    </td>
    <td style="text-align: center;">
      For connecting the stereo head camera
    </td>
  </tr>
</table>


## 5.2 💽 Data Collection Devices

> The following items are optional devices for recording [datasets](https://huggingface.co/unitreerobotics). Parameters, links, etc. are for **reference only**.

### 5.2.1 Stereo Camera 60 FPS

- Materials

> Compared with the camera in Section 5.2.2, this one increases the frame rate from 30 FPS to 60 FPS, and its mounting dimensions differ.

|       Item        | Quantity |                        Specification                         |                           Remarks                            |
| :---------------: | :------: | :----------------------------------------------------------: | :----------------------------------------------------------: |
| Stereo RGB Camera |    1     | [60FPS, 125°FOV, 60mm baseline](https://e.tb.cn/h.S2zMNwiUzC9I2H1) |                  For robot head perspective                  |
|  M4x16mm Screws   |    2     |           [Reference](https://amzn.asia/d/cfta55x)           |                 For fastening camera bracket                 |
| M2x5mm/6mm Screws |    8     |           [Reference](https://amzn.asia/d/1msRa5B)           | For fastening (camera - camera bracket) and (camera bracket - camera cover) |

- 3D Printing Parts

<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%; text-align: center;">
  <colgroup>
    <col style="width: 20%;">
    <col style="width: 20%;">
    <col style="width: 20%;">
    <col style="width: 20%;">
    <col style="width: 20%;">
  </colgroup>
  <tr>
    <th>Item</th>
    <th>Camera Bracket</th>
    <th>Camera Cover Plate</th>
    <th>USB-Type-C Clamp</th>
    <th>Download Link</th>
  </tr>
  <tr>
    <td>
      <img src="https://oss-global-cdn.unitree.com/static/e5ca0cc978cb4b48b693869bbc0e2a36_1023x885.png" style="max-width:45%; margin-bottom:5px;"/><br />
      <b>Classic Head (98mm)</b>
    </td>
    <td><img src="https://oss-global-cdn.unitree.com/static/d8b0d8faa2d94a84a292bc4c26c65f2a_1920x1080.png" style="max-width:100%;"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/caa6e17e8fba45b1a53c9109e9a6a9a4_1509x849.png" style="max-width:50%;"/></td>
    <td align="center"><img src="https://oss-global-cdn.unitree.com/static/ea8edf0b4dd54ea792935eee9b70f550_1443x641.png" style="max-width:30%;"/></td>
    <td><a href="https://oss-global-cdn.unitree.com/static/477103c571dc46f99ec6e0b57b3b3be6.zip">📥 Classic 3D Printing Parts</a></td>
  </tr>
  <tr>
    <td>
      <img src="https://oss-global-cdn.unitree.com/static/af9f379642e044bc9e88040b2c33a4c4_1110x904.png" style="max-width:50%; margin-bottom:5px;"/><br />
      <b>Renewed Head (88mm)</b>
    </td>
    <td><img src="https://oss-global-cdn.unitree.com/static/d8b0d8faa2d94a84a292bc4c26c65f2a_1920x1080.png" style="max-width:100%;"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/caa6e17e8fba45b1a53c9109e9a6a9a4_1509x849.png" style="max-width:50%;"/></td>
    <td align="center"><img src="https://oss-global-cdn.unitree.com/static/ea8edf0b4dd54ea792935eee9b70f550_1443x641.png" style="max-width:30%;"/></td>
    <td><a href="https://oss-global-cdn.unitree.com/static/950f53b95d5943589e278241b59c86ff.zip">📥 Renewed 3D Printing Parts</a></td>
  </tr>
</table>

### 5.2.2 Stereo Camera 30 FPS

- Materials

|       Item        | Quantity |                        Specification                         |                           Remarks                            |
| :---------------: | :------: | :----------------------------------------------------------: | :----------------------------------------------------------: |
|   Stereo Camera   |    1     | [30FPS, 125°FOV, 60mm baseline](http://e.tb.cn/h.TaZxgkpfWkNCakg) |                  For robot head perspective                  |
|  M4x16mm Screws   |    2     |           [Reference](https://amzn.asia/d/cfta55x)           |                 For fastening camera bracket                 |
| M2x5mm/6mm Screws |    8     |           [Reference](https://amzn.asia/d/1msRa5B)           | For fastening (camera - camera bracket) and (camera bracket - camera cover) |

- 3D Printing Parts

<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%; text-align: center;">
  <colgroup>
    <col style="width: 20%;">
    <col style="width: 25%;">
    <col style="width: 25%;">
    <col style="width: 30%;">
  </colgroup>
  <tr>
    <th>Item</th>
    <th>Camera Bracket</th>
    <th>Camera Cover Plate</th>
    <th>Download Link</th>
  </tr>
  <tr>
    <td>
      <img src="https://oss-global-cdn.unitree.com/static/e5ca0cc978cb4b48b693869bbc0e2a36_1023x885.png" style="max-width:45%; margin-bottom:5px;"/><br />
      <b>Classic Head (98mm)</b>
    </td>
    <td><img src="https://oss-global-cdn.unitree.com/static/d8b0d8faa2d94a84a292bc4c26c65f2a_1920x1080.png" style="max-width:100%;"/></td>
    <td>None</td>
    <td><a href="https://oss-global-cdn.unitree.com/static/39dea40900784b199bcba31e72c906b9.zip">📥 Classic 3D Printing Parts</a></td>
  </tr>
  <tr>
    <td>
      <img src="https://oss-global-cdn.unitree.com/static/af9f379642e044bc9e88040b2c33a4c4_1110x904.png" style="max-width:50%; margin-bottom:5px;"/><br />
      <b>Renewed Head (88mm)</b>
    </td>
    <td><img src="https://oss-global-cdn.unitree.com/static/d8b0d8faa2d94a84a292bc4c26c65f2a_1920x1080.png" style="max-width:100%;"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/caa6e17e8fba45b1a53c9109e9a6a9a4_1509x849.png" style="max-width:50%;"/></td>
    <td><a href="https://oss-global-cdn.unitree.com/static/58e300cc99da48f4a4977998c48cefa3.zip">📥 Renewed 3D Printing Parts</a></td>
  </tr>
</table>

### 5.2.3 G1 Wrist RealSense D405

- Materials

|      Item      | Quantity |                        Specification                         |                           Remarks                            |
| :------------: | :------: | :----------------------------------------------------------: | :----------------------------------------------------------: |
| RealSense D405 |    2     | [Website](https://www.intelrealsense.com/depth-camera-d405/) |       For G1 robot left and right wrist perspectives         |
|   USB3.0 Hub   |    1     | [Issue](https://github.com/IntelRealSense/librealsense/issues/24) | Choose a high-quality hub; recommended to connect to [Type-C #9](https://support.unitree.com/home/en/G1_developer/about_G1) |
|  M3-1 Hex Nut  |    4     |             [Reference](https://a.co/d/gQaLtHD)              |                     For wrist fastening                      |
|  M3x12 Screw   |    4     |           [Reference](https://amzn.asia/d/aU9NHSf)           |                     For wrist fastening                      |
|   M3x6 Screw   |    4     |           [Reference](https://amzn.asia/d/0nEz5dJ)           |                     For wrist fastening                      |

- 3D Printing Parts

|           Item           | Quantity |            Remarks             |                        Download Link                         |
| :----------------------: | :------: | :----------------------------: | :----------------------------------------------------------: |
| D405 Wrist Ring Dex3-1 Bracket |    2     | To be used with the wrist camera bracket (M4010 wrist motor) | [📥 STEP](https://github.com/unitreerobotics/xr_teleoperate/blob/7cd188c1657ad4df97cfcd44e9f35bac937f7f2b/hardware/left_wrist_D405_camera_mount.STEP) |
| Left Wrist Camera Dex3-1 Bracket (M4010 wrist motor) |    1     | For mounting the left wrist D405 camera  | [📥 STEP](https://github.com/unitreerobotics/xr_teleoperate/blob/7cd188c1657ad4df97cfcd44e9f35bac937f7f2b/hardware/right_wrist_D405_camera_mount.STEP) |
| Right Wrist Camera Dex3-1 Bracket (M4010 wrist motor) |    1     | For mounting the right wrist D405 camera | [📥 STEP](https://github.com/unitreerobotics/xr_teleoperate/blob/7cd188c1657ad4df97cfcd44e9f35bac937f7f2b/hardware/wrist_ring_mount.STEP) |
| D405 Camera Dex1-1 Bracket |    1     | For mounting the Dex1-1 D405 camera | [📥 STEP](https://drive.google.com/file/d/1YmQHXSf-elHDRNwJMGQlAI7aqd9TGmN5/view?usp=sharing) |

### 5.2.4 G1 Wrist Monocular Camera

- Materials

|       Item        | Quantity |                        Specification                         |                      Remarks                       |
| :---------------: | :------: | :----------------------------------------------------------: | :------------------------------------------------: |
| Monocular Camera  |    2     | [60FPS, 160° FOV](https://e.tb.cn/h.S2YWUJan6ZP8Wqv?tk=MqHK4uvWlLk) |   For G1 robot wrist (M4010 motors) left & right   |
|    USB3.0 Hub     |    1     | [Reference](https://e.tb.cn/h.S2QB8hVuKbNfqb9?tk=XsBL4uwn2Ch) |          For connecting two wrist cameras          |
|   M3-1 Hex Nut    |    4     |             [Reference](https://a.co/d/gQaLtHD)              |                For wrist fastening                 |
|    M3x12 Screw    |    4     |           [Reference](https://amzn.asia/d/aU9NHSf)           |         For fastening wrist bracket and ring         |
|   M2.5x5 Screw    |    4     |           [Reference](https://amzn.asia/d/0nEz5dJ)           |     For fastening cable clip and wrist bracket     |
| M2x5mm/6mm Screws |    8     |           [Reference](https://amzn.asia/d/1msRa5B)           | For fastening (camera-bracket) and (bracket-cover) |

- 3D Printing Parts

<table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%; text-align: center;">
  <tr>
    <th>End-Effector</th>
    <th>Camera Bracket</th>
    <th>Wrist Ring</th>
    <th>Camera Cover Plate</th>
    <th>Cable Clip</th>
    <th>Download Link</th>
  </tr>
  <tr>
    <td><a href="https://www.unitree.com/Dex1-1">Unitree Dex1-1</a></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/e21bd12e56b8442cb460aae93ca85443_1452x1047.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/d867000b2cd6496595e5ca373b9e39a9_1133x683.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/eb98c4f275db4d86b94e77746589cd94_1361x712.png" width="120"/></td>
    <td rowspan="3" valign="middle">
      <img src="https://oss-global-cdn.unitree.com/static/feefe9b679c34c5b8e88274174e23266_1095x689.png" width="120"/>
    </td>
    <td rowspan="3" valign="middle">
      <a href="https://oss-global-cdn.unitree.com/static/ff287f8f700948b5a30e3f4331a46b51.zip">📥 Download 3D Printing Parts</a>
    </td>
  </tr>
  <tr>
    <td><a href="https://www.unitree.com/Dex3-1">Unitree Dex3-1</a></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/69e27c2433694c609f47f8c87265de90_893x741.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/8d49682d9f4a49cdbcfba8660de88b81_982x588.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/901421b01ca440d8bb8459feed1e42ff_1168x754.png" width="120"/></td>
  </tr>
  <tr>
    <td>
      <a href="https://support.unitree.com/home/en/G1_developer/inspire_dfx_dexterous_hand">Inspire DFX Hand</a> /
      <a href="https://support.unitree.com/home/en/G1_developer/brainco_hand">Brainco Hand</a>
    </td>
    <td><img src="https://oss-global-cdn.unitree.com/static/b83d56bd28e64ccfb6c30bdcedfb536d_801x887.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/763521d9313e4648b9dd23a3c11d8291_752x906.png" width="120"/></td>
    <td><img src="https://oss-global-cdn.unitree.com/static/68ed3a1ef0434801adbb73f2f45799e8_808x865.png" width="120"/></td>
  </tr>
</table>


## 5.3 🔨 Installation Illustrations (Partial)

<table>
    <tr>
        <th align="center">Item</th>
        <th align="center" colspan="2">Simulation</th>
        <th align="center" colspan="2">Real Device</th>
    </tr>
    <tr>
        <td align="center">Head</td>
        <td align="center">
            <p align="center">
                <img src="./img/head_camera_mount.png" alt="head" width="100%">
                <figcaption>Head Bracket</figcaption>
            </p>
        </td>
        <td align="center">
            <p align="center">
                <img src="./img/head_camera_mount_install.png" alt="head" width="80%">
                <figcaption>Assembly Side View</figcaption>
            </p>
        </td>
        <td align="center" colspan="2">
            <p align="center">
                <img src="./img/real_head.jpg" alt="head" width="20%">
                <figcaption>Assembly Front View</figcaption>
            </p>
        </td>
    </tr>
    <tr>
        <td align="center">Wrist</td>
        <td align="center" colspan="2">
            <p align="center">
                <img src="./img/wrist_and_ring_mount.png" alt="wrist" width="100%">
                <figcaption>Wrist Ring & Camera bracket</figcaption>
            </p>
        </td>
        <td align="center">
            <p align="center">
                <img src="./img/real_right_hand.jpg" alt="wrist" width="50%">
                <figcaption>Assembly Right Hand</figcaption>
            </p>
        </td>
        <td align="center">
            <p align="center">
                <img src="./img/real_left_hand.jpg" alt="wrist" width="50%">
                <figcaption>Assembly Left Hand</figcaption>
            </p>
        </td>
    </tr>
</table>


> Note: As shown in the red circles, the wrist ring bracket must align with the wrist joint seam.
