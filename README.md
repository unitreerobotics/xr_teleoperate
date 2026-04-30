<div align="center">
  <h1 align="center">xr_teleoperate</h1>
  <a href="https://www.unitree.com/" target="_blank">
    <img src="https://www.unitree.com/images/0079f8938336436e955ea3a98c4e1e59.svg" alt="Unitree LOGO" width="15%">
  </a>
  <p align="center">
    <a> English </a> | <a href="README_zh-CN.md">中文</a> | <a href="README_ja-JP.md">日本語</a>
  </p>
  <p align="center">
    <a href="https://github.com/unitreerobotics/xr_teleoperate/wiki" target="_blank"> <img src="https://img.shields.io/badge/GitHub-Wiki-181717?logo=github" alt="Unitree LOGO"></a> <a href="https://discord.gg/ZwcVwxv5rq" target="_blank"><img src="https://img.shields.io/badge/-Discord-5865F2?style=flat&logo=Discord&logoColor=white" alt="Unitree LOGO"> <a href="https://deepwiki.com/unitreerobotics/xr_teleoperate"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a> </a>
  </p>
</div>


# 📺 Video Demo

<p align="center">
  <table>
    <tr>
      <td align="center" width="50%">
        <a href="https://www.youtube.com/watch?v=OTWHXTu09wE" target="_blank">
          <img src="https://img.youtube.com/vi/OTWHXTu09wE/maxresdefault.jpg" alt="Video 1" width="75%">
        </a>
        <p><b> G1 (29DoF) + Dex3-1 </b></p>
      </td>
      <td align="center" width="50%">
        <a href="https://www.youtube.com/watch?v=pNjr2f_XHoo" target="_blank">
          <img src="https://img.youtube.com/vi/pNjr2f_XHoo/maxresdefault.jpg" alt="Video 2" width="75%">
        </a>
        <p><b> H1_2 (Arm 7DoF) </b></p>
      </td>
    </tr>
  </table>
</p>


# 🔖[Release Note](CHANGELOG.md)

## 🏷️ v1.5 (2025.12.29)

- support simulation
- add CycloneDDS interface name parameter
- [add caching to speed-up urdf loading](https://github.com/unitreerobotics/xr_teleoperate/commit/6cab654620735bfa347c1cd32a0d8c0c1e6ec343)
- ...



# 0. 📖 Introduction

This repository implements **teleoperation** control of a **Unitree humanoid robot** using **XR (Extended Reality) devices** (such as Apple Vision Pro, PICO 4 Ultra Enterprise, or Meta Quest 3). 

> If you have never worked with a Unitree robot before, please at least read up to the “Application Development” chapter in the [official documentation](https://support.unitree.com/main/en) first.
Additionally, the [Wiki of this repo](https://github.com/unitreerobotics/xr_teleoperate/wiki) contains a wealth of background knowledge that you can reference at any time.

Here are the required devices and wiring diagram,

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/55fb9cd245854810889855010da296f7_3415x2465.png">
    <img src="https://oss-global-cdn.unitree.com/static/55fb9cd245854810889855010da296f7_3415x2465.png" alt="System Diagram" style="width: 100%;">
  </a>
</p>


The currently supported devices in this repository:

<table>
  <tr>
    <th align="center">🤖 Robot</th>
    <th align="center">⚪ Status</th>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/g1" target="_blank">G1 (29 DoF)</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/g1" target="_blank">G1 (23 DoF)</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/h1" target="_blank">H1 (4‑DoF arm)</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/h1" target="_blank">H1_2 (7‑DoF arm)</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/Dex1-1" target="_blank">Dex1‑1 gripper</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/en/Dex3-1" target="_blank">Dex3‑1 dexterous hand</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td align="center"><a href="https://support.unitree.com/home/en/G1_developer/inspire_dfx_dexterous_hand" target="_blank">Inspire dexterous hand</a></td>
    <td align="center">✅ Complete</td>
  </tr>
  <tr>
    <td style="text-align: center;"> <a href="https://www.brainco-hz.com/docs/revolimb-hand/en/revo2/parameters.html" target="_blank"> BrainCo dexterous hand </td>
    <td style="text-align: center;"> &#9989; Complete </td>
  </tr>
  <tr>
    <td align="center"> ··· </td>
    <td align="center"> ··· </td>
  </tr>
</table>



# 1. 📦 Installation

We tested our code on Ubuntu 20.04 and Ubuntu 22.04, other operating systems may be configured differently. This document primarily describes the **default mode**.

For more information, you can refer to [Official Documentation ](https://support.unitree.com/home/en/Teleoperation) and [OpenTeleVision](https://github.com/OpenTeleVision/TeleVision).

## 1.1 📥 basic

```bash
# Create a conda environment
(base) unitree@Host:~$ conda create -n tv python=3.10 pinocchio=3.1.0 numpy=1.26.4 -c conda-forge
(base) unitree@Host:~$ conda activate tv
# Clone this repo
(tv) unitree@Host:~$ git clone https://github.com/unitreerobotics/xr_teleoperate.git
(tv) unitree@Host:~$ cd xr_teleoperate
# Shallow clone submodule
(tv) unitree@Host:~/xr_teleoperate$ git submodule update --init --depth 1
```

```bash
# Install teleimager submodule
(tv) unitree@Host:~/xr_teleoperate$ cd teleop/teleimager
(tv) unitree@Host:~/xr_teleoperate/teleop/teleimager$ pip install -e . --no-deps
```

```bash
# Install televuer submodule
(tv) unitree@Host:~/xr_teleoperate$ cd teleop/televuer
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ pip install -e .

# Configure SSL certificates for the televuer module so that XR devices (e.g., Pico / Quest / Apple Vision Pro) can securely connect via HTTPS / WebRTC
# 1. Generate certificate files
# 1.1 For Pico / Quest XR devices
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem
# 1.2 For Apple Vision Pro
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out rootCA.key 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 365 -out rootCA.pem -subj "/CN=xr-teleoperate"
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out key.pem 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -new -key key.pem -out server.csr -subj "/CN=localhost"
# Create server_ext.cnf file with the following content (IP.2 should match your host IP, e.g., 192.168.123.2. Use ifconfig or similar to check)
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ vim server_ext.cnf
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
IP.1 = 192.168.123.164
IP.2 = 192.168.123.2
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl x509 -req -in server.csr -CA rootCA.pem -CAkey rootCA.key -CAcreateserial -out cert.pem -days 365 -sha256 -extfile server_ext.cnf
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ ls
build  cert.pem  key.pem  LICENSE  pyproject.toml  README.md  rootCA.key  rootCA.pem  rootCA.srl  server.csr  server_ext.cnf  src  test
# Copy rootCA.pem to Apple Vision Pro via AirDrop and install it

# Enable firewall
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ sudo ufw allow 8012

# 2. Configure certificate paths, choose one method
# 2.1 User config directory (optional)
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ mkdir -p ~/.config/xr_teleoperate/
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ cp cert.pem key.pem ~/.config/xr_teleoperate/
# 2.2 Environment variables (optional)
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_CERT="$HOME/xr_teleoperate/teleop/televuer/cert.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_KEY="$HOME/xr_teleoperate/teleop/televuer/key.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ source ~/.bashrc
```



## 1.2 🕹️ unitree_sdk2_python

```bash
# Install unitree_sdk2_python library which handles communication with the robot
(tv) unitree@Host:~$ git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
(tv) unitree@Host:~$ cd unitree_sdk2_python
(tv) unitree@Host:~/unitree_sdk2_python$ pip install -e .
```

> **Note 1:** For `xr_teleoperate` versions **v1.1 and above**, please ensure that the `unitree_sdk2_python` repository is checked out to a commit **equal to or newer than** [404fe44d76f705c002c97e773276f2a8fefb57e4](https://github.com/unitreerobotics/unitree_sdk2_python/commit/404fe44d76f705c002c97e773276f2a8fefb57e4).
>
> **Note 2**: The [unitree_dds_wrapper](https://github.com/unitreerobotics/unitree_dds_wrapper) in the original h1_2 branch was a temporary version. It has now been fully migrated to the official Python-based control and communication library: [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python).
>
> **Note 3**: All identifiers in front of the command are meant for prompting: **Which device and directory the command should be executed on**.
>
> In the Ubuntu system's `~/.bashrc` file, the default configuration is: `PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '`
>
> Taking the command `(tv) unitree@Host:~$ pip install meshcat` as an example:
>
> - `(tv)` Indicates the shell is in the conda environment named `tv`.
> - `unitree@Host:~` Shows the user `\u` `unitree` is logged into the device `\h` `Host`, with the current working directory `\w` as `$HOME`.
> - `$` shows the current shell is Bash (for non-root users).
> - `pip install meshcat` is the command `unitree` wants to execute on `Host`.
>
> You can refer to [Harley Hahn's Guide to Unix and Linux](https://www.harley.com/unix-book/book/chapters/04.html#H)  and  [Conda User Guide](https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html) to learn more.



## 1.3 🚀 Launch Parameter Description

- **Basic control parameters**

|      ⚙️ Parameter      |                        📜 Description                         |                     🔘 Available Options                      |     📌 Default     |
| :-------------------: | :----------------------------------------------------------: | :----------------------------------------------------------: | :---------------: |
|     `--frequency`     |            Set the FPS for recording and control             |                  Any reasonable float value                  |       30.0        |
|    `--input-mode`     |       Choose XR input mode (how to control the robot)        |   `hand` (hand tracking)`controller` (controller tracking)   |      `hand`       |
|   `--display-mode`    |  Choose XR display mode (how to view the robot perspective)  | `immersive` (immersive)`ego` (pass-through + small first-person window)`pass-through` (pass-through only) |    `immersive`    |
|        `--arm`        |      Select the robot arm type (see 0. 📖 Introduction)       |                 `G1_29` `G1_23` `H1_2` `H1`                  |      `G1_29`      |
|        `--ee`         | Select the end-effector type of the arm (see 0. 📖 Introduction) |     `dex1` `dex3` `inspire_ftp` `inspire_dfx` `brainco`      |       None        |
|   `--img-server-ip`   | Set the image server IP address for receiving image streams and configuring WebRTC signaling |                        `IPv4` address                        | `192.168.123.164` |
| `--network-interface` |    Set the network interface for CycloneDDS communication    |                    Network Interface Name                    |      `None`       |

- **Mode switch parameters**

| ⚙️ Parameter  |                        📜 Description                         |
| :----------: | :----------------------------------------------------------: |
|  `--motion`  | **Enable motion control mode** When enabled, the teleoperation program can run alongside the robot’s motion control program.In **hand tracking** mode, the [R3 controller](https://www.unitree.com/cn/R3) can be used to control normal robot walking; in **controller tracking** mode, joysticks can also control the robot’s movement.<br />Note: Only `Regular mode` (R1+X) is supported, `Running mode` (R2+A) is not supported. |
| `--headless` | **Enable headless mode** For running the program on devices without a display, e.g., the Development Computing Unit (PC2). |
|   `--sim`    | **Enable [simulation mode](https://github.com/unitreerobotics/unitree_sim_isaaclab)** |
|   `--ipc`    | **Inter-process communication mode** Allows controlling the xr_teleoperate program’s state via IPC. Suitable for interaction with agent programs. |
| `--affinity` | **CPU affinity mode** Set CPU core affinity. If you are unsure what this is, do not set it. |
|  `--record`  | **Enable data recording mode** Press **r** to start teleoperation, then **s** to start recording; press **s** again to stop and save the episode. Press **s** repeatedly to repeat the process. |
|  `--task-*`  | Configure the save path, target, description, and steps of the recorded task. |

## 1.4 🔄 State Transition Diagram

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/712c312b0ac3401f8d7d9001b1e14645_11655x4305.jpg">
    <img src="https://oss-global-cdn.unitree.com/static/712c312b0ac3401f8d7d9001b1e14645_11655x4305.jpg" alt="System Diagram" style="width: 85%;">
  </a>
</p>

# 2. 💻 Simulation Deployment

## 2.1 📥 Environment Setup


First, install [unitree_sim_isaaclab](https://github.com/unitreerobotics/unitree_sim_isaaclab). Follow that repo’s README.

Then launch the simulation with a G1(29 DoF) and Dex3 hand configuration:

```bash
(base) unitree@Host:~$ conda activate unitree_sim_env
(unitree_sim_env) unitree@Host:~$ cd ~/unitree_sim_isaaclab
(unitree_sim_env) unitree@Host:~/unitree_sim_isaaclab$ python sim_main.py --device cpu --enable_cameras --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint --enable_dex3_dds --robot_type g129
```

💥💥💥 NOTICE❗

> **After simulation starts, click once in the window to activate it.**
>
> The terminal will show:  `controller started, start main loop...`

Here is the simulation GUI:

<p align="center">   <a href="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png">     <img src="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png" alt="Simulation UI" style="width: 75%;">   </a> </p>

## 2.2 🚀 Launch

This program supports XR control of a physical robot or in simulation. Choose modes with command-line arguments:

Assuming hand tracking with G1(29 DoF) + Dex3 in simulation with recording:

```bash
(tv) unitree@Host:~$ cd ~/xr_teleoperate/teleop/
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --xr-mode=hand --arm=G1_29 --ee=dex3 --sim --record
# Simplified (defaults apply):
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --ee=dex3 --sim --record
```

After the program starts, the terminal shows:

<p align="center">   <a href="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png">     <img src="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png" alt="Terminal Start Log" style="width: 75%;">   </a> </p>

Next steps:

1. Wear your XR headset (e.g. Apple Vision Pro, PICO4, etc.)

2. Connect to the corresponding Wi‑Fi

3. Only proceed if your head camera has WebRTC enabled (`cam_config_server.yaml → head_camera → enable_webrtc: true`); otherwise jump to Step 4. Open a browser (e.g. Safari or PICO Browser) and go to:  
   **https://192.168.123.164:60001**

   > **Note 1:** This IP is the address of **PC2**—the machine running teleimager service.  
   > **Note 2:** You may see a warning page like step 4. Click **Advanced**, then **Proceed to IP (unsafe)**. Once the page loads, press the **start** button in the top-left corner; if you see the head-camera preview, the check is successful.
   >
   > <p align="center">
   >   <a href="https://oss-global-cdn.unitree.com/static/777f9c6f42d74eb2a6438d1509a73025_2475x1574.jpg">
   >     <img src="https://oss-global-cdn.unitree.com/static/777f9c6f42d74eb2a6438d1509a73025_2475x1574.jpg" alt="webrtc_unsafe" style="width: 50%;">
   >   </a>
   > </p>
   >
   > **Note 3:** This step serves two purposes:  
   >
   > 1. Verify that the teleimager service is running correctly.  
   > 2. Manually trust the WebRTC self-signed certificate.  
   >
   > Once this has been done on the same device with the same certificate, you can skip it on subsequent launches.

4. Open a browser (e.g. Safari or PICO Browser) and go to:  `https://192.168.123.2:8012/?ws=wss://192.168.123.2:8012`

   > **Note 1**: This IP must match your **Host** IP (check with `ifconfig`).
   >
   > **Note 2**: You may see a warning page. Click **Advanced**, then **Proceed to IP (unsafe)**.

   <p align="center">
     <a href="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png">
       <img src="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png" alt="vuer_unsafe" style="width: 50%;">
     </a>
   </p>

5. In the Vuer web, click **Virtual Reality**. Allow all prompts to start the VR session.

   <p align="center">  <a href="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png">    <img src="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png" alt="Vuer UI" style="width: 75%;">  </a> </p>

6. You’ll see the robot’s first-person view in the headset. The terminal prints connection info:

   ```bash
   websocket is connected. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
   default socket worker is up, adding clientEvents
   Uplink task running. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
   ```

7. Align your arm to the **robot’s initial pose** to avoid sudden movements at start:

   <p align="center">  <a href="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png">    <img src="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png" alt="Initial Pose" style="width: 25%;">  </a> </p>

8. Press **r** in the terminal to begin teleoperation. You can now control the robot arm and dexterous hand.

9. During teleoperation, press **s** to start recording; press **s** again to stop and save. Repeatable process.

<p align="center">  <a href="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png">    <img src="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png" alt="Recording Process" style="width: 75%;">  </a> </p>

> **Note 1**: Recorded data is stored in `xr_teleoperate/teleop/utils/data` by default, with usage instructions at this repo:  [unitree_IL_lerobot](https://github.com/unitreerobotics/unitree_IL_lerobot/tree/main?tab=readme-ov-file#data-collection-and-conversion).
>
> **Note 2**: Please pay attention to your disk space size during data recording.
>
> **Note 3**: In v1.4 and above, the “record image” window has been removed.

## 2.3 🔚 Exit

Press **q** in the terminal (or “record image” window) to quit.



# 3. 🤖 Physical Deployment

Physical deployment steps are similar to simulation, with these key differences:

## 3.1 🖼️ Image Service

In the simulation environment, the image service is automatically enabled. For physical deployment, you need to manually start the image service based on your specific camera hardware. The steps are as follows:

1. Install the image service program on the **Development Computing Unit PC2** of the Unitree robot (G1/H1/H1_2, etc.)

   ```bash
   # SSH into PC2 and download the image service repository
   
   (base) unitree@PC2:~$ cd ~
   (base) unitree@PC2:~$ git clone https://github.com/silencht/teleimager
   
   # Configure the environment according to the instructions in the teleimager repository README: https://github.com/silencht/teleimager/blob/main/README.md
   ```

2. On the **local host**, execute the following commands:

   ```bash
   # Copy the `key.pem` and `cert.pem` files configured in Section 1.1 from the **local host** `xr_teleoperate/teleop/televuer` directory to the corresponding path on PC2
   
   # These two files are required by teleimager to start the WebRTC service
   (tv) unitree@Host:~$ scp ~/xr_teleoperate/teleop/televuer/key.pem ~/xr_teleoperate/teleop/televuer/cert.pem unitree@192.168.123.164:~/teleimager
   
   # On PC2, configure the certificate path according to the teleimager repository README, for example:
   (teleimager) unitree@PC2:~$ cd teleimager
   (teleimager) unitree@PC2:~$ mkdir -p ~/.config/xr_teleoperate/
   (teleimager) unitree@PC2:~/teleimager$ cp cert.pem key.pem ~/.config/xr_teleoperate/
   ```

3. On the **development computing unit PC2**, configure `cam_config_server.yaml` according to the teleimager documentation and start the image service.

   ```bash
   (teleimager) unitree@PC2:~/image_server$ python -m teleimager.image_server
   
   # The following command works the same way
   (teleimager) unitree@PC2:~/image_server$ teleimager-server
   ```

4. On the **local host**, execute the following command to subscribe to the images

   ```bash
   (tv) unitree@Host:~$ cd ~/xr_teleoperate/teleop/teleimager/src
   (tv) unitree@Host:~/xr_teleoperate/teleop/teleimager/src$ python -m teleimager.image_client --host 192.168.123.164
   
   # If the WebRTC image stream is set up, you can also open the URL [https://192.168.123.164:60001](https://192.168.123.164:60001) in a browser and click the Start button to test.
   ```

   

## 3.2 ✋ Inspire Hand Service (optional)

> **Note 1**: Skip this if your config does not use the Inspire hand.
>
> **Note 2**: For G1 robot with [Inspire DFX hand](https://support.unitree.com/home/en/G1_developer/inspire_dfx_dexterous_hand), related issue [#46](https://github.com/unitreerobotics/xr_teleoperate/issues/46).
>
> **Note 3**: For [Inspire FTP hand]((https://support.unitree.com/home/en/G1_developer/inspire_ftp_dexterity_hand)), related issue [#48](https://github.com/unitreerobotics/xr_teleoperate/issues/48). FTP dexterous hand is now supported. Please refer to the `--ee` parameter for configuration.

First, use [this URL: DFX_inspire_service](https://github.com/unitreerobotics/DFX_inspire_service) to clone the dexterous hand control interface program. And Copy it to **PC2** of  Unitree robots. 

On Unitree robot's **PC2**, execute command:

```bash
unitree@PC2:~$ sudo apt install libboost-all-dev libspdlog-dev
# Build project
unitree@PC2:~$ cd DFX_inspire_service && mkdir build && cd build
unitree@PC2:~/DFX_inspire_service/build$ cmake ..
unitree@PC2:~/DFX_inspire_service/build$ make -j6

# (For unitree g1) Terminal 1.
unitree@PC2:~/DFX_inspire_service/build$ sudo ./inspire_g1
# or (For unitree h1) Terminal 1.
unitree@PC2:~/DFX_inspire_service/build$ sudo ./inspire_h1 -s /dev/ttyUSB0

# Terminal 2. Run example
unitree@PC2:~/DFX_inspire_service/build$ ./hand_example
```

If two hands open and close continuously, it indicates success. Once successful, close the `./hand_example` program in Terminal 2.



## 3.3 ✋ BrainCo Hand Service (Optional)

Please refer to the [Repo README](https://github.com/unitreerobotics/brainco_hand_service) for setup instructions.

## 3.4 ✋ Unitree Dex1_1 Service (Optional)

Please refer to the [Repo README](https://github.com/unitreerobotics/dex1_1_service) for setup instructions.

## 3.5 🚀 Launch

>  ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
>  1. Everyone must keep a safe distance from the robot to prevent any potential danger!
>  2. Please make sure to read the [Official Documentation](https://support.unitree.com/home/en/Teleoperation) at least once before running this program.
>  3. To use motion mode (with `--motion`), ensure the robot is in control mode (via [R3 remote](https://www.unitree.com/R3)).
>  5. In motion mode:
>    - Right controller **A** = Exit teleop
>    - Both joysticks pressed = soft emergency stop (switch to damping mode)
>    - Left joystick = drive directions; 
>    - right joystick = turning; 
>    - max speed is limited in the code.

Same as simulation but follow the safety warnings above.

## 3.6 🔚 Exit

> ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
> To avoid damaging the robot, it is recommended to position the robot's arms close to the initial pose before pressing **q** to exit.
>
> - In **Debug Mode**: After pressing the exit key, both arms will return to the robot's **initial pose** within 5 seconds, and then the control will end.
>
> - In **Motion Mode**: After pressing the exit key, both arms will return to the robot's **motion control pose** within 5 seconds, and then the control will end.

Same as simulation but follow the safety warnings above.



# 4. 🗺️ Codebase Overview

```
xr_teleoperate/
│
├── assets                    [Stores robot URDF-related files]
│
├── teleop
│   ├── teleimager            [New image service library, supporting multiple features]
│   │
│   ├── televuer
│   │      ├── src/televuer
│   │         ├── television.py       [Captures head, wrist, and hand/controller data from XR devices using Vuer]
│   │         ├── tv_wrapper.py       [Post-processing of captured data]
│   │      ├── test
│   │         ├── _test_television.py [Test program for television.py]
│   │         ├── _test_tv_wrapper.py [Test program for tv_wrapper.py]
│   │
│   ├── robot_control
│   │      ├── src/dex-retargeting [Dexterous hand retargeting algorithm library]
│   │      ├── robot_arm_ik.py     [Inverse kinematics for the arm]
│   │      ├── robot_arm.py        [Controls dual-arm joints and locks other parts]
│   │      ├── hand_retargeting.py [Wrapper for the dexterous hand retargeting library]
│   │      ├── robot_hand_inspire.py  [Controls Inspire dexterous hand]
│   │      ├── robot_hand_unitree.py  [Controls Unitree dexterous hand]
│   │
│   ├── utils
│   │      ├── episode_writer.py          [Used to record data for imitation learning]
│   │      ├── weighted_moving_filter.py  [Filter for joint data]
│   │      ├── rerun_visualizer.py        [Visualizes recorded data]
│   │      ├── ipc.py                     [Handles inter-process communication with proxy programs]
│   │      ├── motion_switcher.py         [Switches motion control states]
│   │      ├── sim_state_topic.py         [For simulation deployment]
│   │
│   └── teleop_hand_and_arm.py    [Startup script for teleoperation]

```

# 5. 🛠️ Hardware

please see [Device document](Device.md).



# 6. 🙏 Acknowledgement

This code builds upon following open-source code-bases. Please visit the URLs to see the respective LICENSES:

1. https://github.com/OpenTeleVision/TeleVision
2. https://github.com/dexsuite/dex-retargeting
3. https://github.com/vuer-ai/vuer
4. https://github.com/stack-of-tasks/pinocchio
5. https://github.com/casadi/casadi
6. https://github.com/meshcat-dev/meshcat-python
7. https://github.com/zeromq/pyzmq
8. https://github.com/Dingry/BunnyVisionPro
9. https://github.com/unitreerobotics/unitree_sdk2_python
10. https://github.com/ARCLab-MIT/beavr-bot

# 7. 📝 Citation

```
@misc{xr-teleoperate,
  author       = {{Unitree Robotics}},
  title        = {{XR-Teleoperate}: An Open-Source Teleoperation Framework and Data Collection Toolkit for Embodied Intelligence},
  howpublished = {\url{https://github.com/unitreerobotics/xr_teleoperate}},
  year         = {2024},
  note         = {Accessed: 2026-02}
}
```
