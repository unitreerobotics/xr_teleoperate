<div align="center">
  <h1 align="center">xr_teleoperate</h1>
  <a href="https://www.unitree.com/" target="_blank">
    <img src="https://www.unitree.com/images/0079f8938336436e955ea3a98c4e1e59.svg" alt="Unitree LOGO" width="15%">
  </a>
  <p align="center">
    <a href="README.md"> English </a> | <a href="README_zh-CN.md">中文</a> | <a>日本語</a>
  </p>
  <p align="center">
    <a href="https://github.com/unitreerobotics/xr_teleoperate/wiki" target="_blank"> <img src="https://img.shields.io/badge/GitHub-Wiki-181717?logo=github" alt="Unitree LOGO"></a> <a href="https://discord.gg/ZwcVwxv5rq" target="_blank"><img src="https://img.shields.io/badge/-Discord-5865F2?style=flat&logo=Discord&logoColor=white" alt="Unitree LOGO"> <a href="https://deepwiki.com/unitreerobotics/xr_teleoperate"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a> </a>
  </p>
</div>


# 📺 デモ動画

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


# 🔖 [更新履歴](CHANGELOG.md)

## 🏷️ v1.6 (2026.7.29)

- **H2** ロボットに対応
- **R1** ロボットに対応（`R1_A5` / `R1_A7`）
- **BrainCo** 多指ハンドのコントローラー入力に対応
- デフォルトで頭部ヨー（head-yaw）基準のアーム参照系を使用
- ...



# 0. 📖 イントロダクション

このリポジトリでは、**XR（拡張現実）デバイス**（Apple Vision Pro、PICO 4 Ultra Enterprise、Meta Quest 3 など）を使用して、**Unitree ヒューマノイドロボット**の**遠隔操作**を実装しています。

> Unitree ロボットを初めて扱う場合は、まず [公式ドキュメント](https://support.unitree.com/main/en) の「アプリケーション開発」章までを一読してください。
>
> また、本リポジトリの [Wiki](https://github.com/unitreerobotics/xr_teleoperate/wiki) にも参考になる背景知識が多数掲載されています。

必要なデバイスと配線図は以下の通りです。

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/55fb9cd245854810889855010da296f7_3415x2465.png">
    <img src="https://oss-global-cdn.unitree.com/static/55fb9cd245854810889855010da296f7_3415x2465.png" alt="システム構成図" style="width: 100%;">
  </a>
</p>


このリポジトリで現在サポートされているデバイス:

<table>
  <tr>
    <th align="center">🤖 ロボット</th>
    <th align="center">⚪ ステータス</th>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/g1" target="_blank">G1 (29 DoF)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/g1" target="_blank">G1 (23 DoF)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/h1" target="_blank">H1 (4自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/h1" target="_blank">H1_2 (7自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/h2" target="_blank">H2 (7自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/R1" target="_blank">R1 (5自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/R1" target="_blank">R1 (7自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/Dex1-1" target="_blank">Dex1‑1グリッパー</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/Dex3-1" target="_blank">Dex3‑1多指ハンド</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://support.unitree.com/home/en/G1_developer/inspire_dfx_dexterous_hand" target="_blank">Inspire多指ハンド</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.brainco-hz.com/docs/revolimb-hand/" target="_blank">BrainCo多指ハンド</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"> ··· </td>
    <td align="center"> ··· </td>
  </tr>
</table>



# 1. 📦 インストール

Ubuntu 20.04 と Ubuntu 22.04 でテスト済みです。他の OS では設定が異なる場合があります。本ドキュメントでは、主に**デフォルトモード**について説明します。

詳細は [公式ドキュメント](https://support.unitree.com/home/zh/Teleoperation) と [OpenTeleVision](https://github.com/OpenTeleVision/TeleVision) を参照してください。

## 1.1 📥 基本設定

```bash
# conda 環境を作成
(base) unitree@Host:~$ conda create -n tv python=3.10 pinocchio=3.1.0 numpy=1.26.4 -c conda-forge
(base) unitree@Host:~$ conda activate tv
# 本リポジトリをクローン
(tv) unitree@Host:~$ git clone https://github.com/unitreerobotics/xr_teleoperate.git
(tv) unitree@Host:~$ cd xr_teleoperate
# サブモジュールを浅くクローン
(tv) unitree@Host:~/xr_teleoperate$ git submodule update --init --depth 1
```

```bash
# teleimager サブモジュールをインストール
(tv) unitree@Host:~/xr_teleoperate$ cd teleop/teleimager
(tv) unitree@Host:~/xr_teleoperate/teleop/teleimager$ pip install -e . --no-deps
```

```bash
# televuer サブモジュールをインストール
(tv) unitree@Host:~/xr_teleoperate$ cd teleop/televuer
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ pip install -e .

# XR デバイス（Pico / Quest / Apple Vision Pro など）が HTTPS / WebRTC 経由で安全に接続できるよう、televuer モジュール用の SSL 証明書を設定
# 1. 証明書ファイルを生成
# 1.1 Pico / Quest などの XR デバイスの場合
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem
# 1.2 Apple Vision Pro の場合
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out rootCA.key 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 365 -out rootCA.pem -subj "/CN=xr-teleoperate"
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out key.pem 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -new -key key.pem -out server.csr -subj "/CN=localhost"
# server_ext.cnf ファイルを作成し、以下の内容を記入（IP.2 はホスト IP に合わせる。例: 192.168.123.2。ifconfig などで確認）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ vim server_ext.cnf
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
IP.1 = 192.168.123.164
IP.2 = 192.168.123.2
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl x509 -req -in server.csr -CA rootCA.pem -CAkey rootCA.key -CAcreateserial -out cert.pem -days 365 -sha256 -extfile server_ext.cnf
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ ls
build  cert.pem  key.pem  LICENSE  pyproject.toml  README.md  rootCA.key  rootCA.pem  rootCA.srl  server.csr  server_ext.cnf  src  test
# AirDrop で rootCA.pem を Apple Vision Pro にコピーしてインストール

# ファイアウォールを開放
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ sudo ufw allow 8012

# 2. 証明書パスを設定（いずれか一方を選択）
# 2.1 ユーザー設定ディレクトリ（任意）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ mkdir -p ~/.config/xr_teleoperate/
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ cp cert.pem key.pem ~/.config/xr_teleoperate/
# 2.2 環境変数（任意）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_CERT="$HOME/xr_teleoperate/teleop/televuer/cert.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_KEY="$HOME/xr_teleoperate/teleop/televuer/key.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ source ~/.bashrc
```

```bash
# dex-retargeting サブモジュールをインストール
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ cd ../robot_control/dex-retargeting/
(tv) unitree@Host:~/xr_teleoperate/teleop/robot_control/dex-retargeting$ pip install -e .
```

```bash
# 本リポジトリに必要なその他の依存ライブラリをインストール
(tv) unitree@Host:~/xr_teleoperate/teleop/robot_control/dex-retargeting$ cd ../../../
(tv) unitree@Host:~/xr_teleoperate$ pip install -r requirements.txt
```

## 1.2 🕹️ unitree_sdk2_python

```bash
# ロボットとの通信・制御を担う unitree_sdk2_python ライブラリをインストール
(tv) unitree@Host:~$ git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
(tv) unitree@Host:~$ cd unitree_sdk2_python
(tv) unitree@Host:~/unitree_sdk2_python$ pip install -e .
```

> **注1**: `xr_teleoperate` の **v1.1 以降**では、`unitree_sdk2_python` リポジトリを [404fe44d76f705c002c97e773276f2a8fefb57e4](https://github.com/unitreerobotics/unitree_sdk2_python/commit/404fe44d76f705c002c97e773276f2a8fefb57e4) **と同等またはそれ以降**の commit にチェックアウトしてください。
>
> **注2**: 元の h1_2 ブランチの [unitree_dds_wrapper](https://github.com/unitreerobotics/unitree_dds_wrapper) は暫定版でした。現在は公式の Python 制御・通信ライブラリ [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) に完全移行済みです。
>
> **注3**: コマンド前の識別子は「どのデバイス・どのディレクトリで実行するか」を示すためのものです。
>
> Ubuntu の `~/.bashrc` のデフォルト設定: `PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '`
>
> 例として `(tv) unitree@Host:~$ pip install meshcat` の場合:
>
> - `(tv)` シェルが conda 環境 `tv` にあることを示す
> - `unitree@Host:~` ユーザー `unitree` がデバイス `Host` にログインし、カレントディレクトリが `$HOME` であることを示す
> - `$` 現在のシェルが Bash（非 root ユーザー）であることを示す
> - `pip install meshcat` は `unitree` が `Host` 上で実行するコマンド
>
> 詳しくは [Harley Hahn's Guide to Unix and Linux](https://www.harley.com/unix-book/book/chapters/04.html#H) と [Conda User Guide](https://docs.conda.io/projects/conda/en/latest/user-guide/getting-started.html) を参照してください。

## 1.3 🚀 起動パラメータ説明

- **基本制御パラメータ**

|      ⚙️ パラメータ      |                          📜 説明                           |                         🔘 選択肢                          |   📌 デフォルト   |
| :-------------------: | :--------------------------------------------------------: | :--------------------------------------------------------: | :---------------: |
|     `--frequency`     |                記録と制御の FPS を設定                     |               適切な範囲内の任意の浮動小数点数              |       30.0        |
|    `--input-mode`     |         XR 入力モードを選択（ロボットの制御方法）          | `hand`（ハンドトラッキング）<br />`controller`（コントローラートラッキング） |      `hand`       |
|   `--display-mode`    |        XR 表示モードを選択（ロボット視点の見方）          | `immersive`（没入型）<br />`ego`（パススルー + 一人称小窓）<br />`pass-through`（パススルーのみ） |    `immersive`    |
|        `--arm`        |         ロボットアームタイプを選択（0. 📖 参照）          | `G1_29`<br />`G1_23`<br />`H1_2`<br />`H1`<br />`H2`<br />`R1_A5`<br />`R1_A7` |      `G1_29`      |
|        `--ee`         |       エンドエフェクタタイプを選択（0. 📖 参照）          | `dex1`<br />`dex1_internal`<br />`dex3`<br />`inspire_ftp`<br />`inspire_dfx`<br />`brainco` |     デフォルト無  |
|   `--img-server-ip`   | 画像サーバーの IP アドレスを設定（画像ストリーム受信・WebRTC シグナリング設定用） |                       `IPv4` アドレス                      | `192.168.123.164` |
| `--network-interface` |            CycloneDDS 通信のネットワークインターフェースを設定            |                    ネットワークIF名                       |      `None`       |

- **モード切替パラメータ**

|  ⚙️ パラメータ  |                            📜 説明                             |
| :----------: | :----------------------------------------------------------: |
|  `--motion`  | 【**運動制御モード**を有効化】<br />有効にすると、ロボットの運動制御プログラム実行下で遠隔操作を行えます。<br />**ハンドトラッキング**モードでは [R3 リモコン](https://www.unitree.com/cn/R3) でロボットを歩行制御でき、**コントローラートラッキング**モードではジョイスティックでも歩行制御できます。<br />注: `Regular mode` (R1+X) のみ対応、`Running mode` (R2+A) は非対応。 |
| `--headless` | 【**ヘッドレスモード**を有効化】<br />ディスプレイのない開発用計算ユニット（PC2）などでの実行に適しています。 |
|   `--sim`    | 【[**シミュレーションモード**](https://github.com/unitreerobotics/unitree_sim_isaaclab)を有効化】 |
|   `--ipc`    | 【プロセス間通信モード】<br />IPC を通じて xr_teleoperate プログラムの状態遷移を制御できます。エージェントプログラムとの連携に適しています。 |
|  `--record`  | 【**データ記録モード**を有効化】<br />**r** で遠隔操作を開始した後、**s** で記録開始、再度 **s** でエピソードの記録を停止・保存します。**s** を繰り返し押すことでこの操作を繰り返せます。 |
| `--task-dir` | 記録データの保存パス。デフォルト：`./utils/data/` |
| `--task-name` | 記録するタスクのファイル名。デフォルト：`pick cube` |
| `--task-goal` | json ファイルに記録するタスク目標。デフォルト：`pick up cube.` |
| `--task-desc` | json ファイルに記録するタスク説明。デフォルト：`task description` |
| `--task-steps` | json ファイルに記録するタスク手順。デフォルト：`step1: do this; step2: do that;` |

## 1.4 🔄 状態遷移図

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/712c312b0ac3401f8d7d9001b1e14645_11655x4305.jpg">
    <img src="https://oss-global-cdn.unitree.com/static/712c312b0ac3401f8d7d9001b1e14645_11655x4305.jpg" alt="System Diagram" style="width: 85%;">
  </a>
</p>

------

# 2. 💻 シミュレーション環境

## 2.1 📥 環境設定

まず [unitree_sim_isaaclab](https://github.com/unitreerobotics/unitree_sim_isaaclab) をインストールしてください。インストール手順は当該リポジトリの README を参照してください。

次に、シミュレーション環境を起動します。G1(29 DoF) と Dex3 多指ハンド構成でシミュレーションを行う場合の起動コマンド例:

```bash
(base) unitree@Host:~$ conda activate unitree_sim_env
(unitree_sim_env) unitree@Host:~$ cd ~/unitree_sim_isaaclab
(unitree_sim_env) unitree@Host:~/unitree_sim_isaaclab$ python sim_main.py --device cpu --enable_cameras --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint --enable_dex3_dds --robot_type g129
```

💥💥💥 注意❗

> **シミュレーション起動後、ウィンドウ内をマウス左クリックしてシミュレーションを有効化してください。**
>
> このとき、ターミナルに `controller started, start main loop...` と表示されます。

シミュレーション画面は以下の通りです:

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png">
    <img src="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png" alt="シミュレーションUI" style="width: 75%;">
  </a>
</p>



## 2.2 🚀 遠隔操作の起動

本プログラムは、XR デバイス（ハンドまたはコントローラー）による実機制御と、仮想シミュレーション上での実行の両方に対応しています。コマンドライン引数で実行方法を設定できます。

1.3 節のパラメータ説明とシミュレーション環境設定に基づき、ここでは**ハンドトラッキング**で G1(29 DoF) + Dex3 多指ハンドを制御し、シミュレーションモードとデータ記録モードを併用する例を示します。

起動コマンド:

```bash
(tv) unitree@Host:~$ cd ~/xr_teleoperate/teleop/
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --input-mode=hand --arm=G1_29 --ee=dex3 --sim --record
# 一部のパラメータにはデフォルト値があるため、次のように簡略化することもできます:
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --ee=dex3 --sim --record
```

プログラムが正常に起動すると、ターミナルに次のような情報が表示されます:

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png">
    <img src="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png" alt="ターミナル起動ログ" style="width: 75%;">
  </a>
</p>

次の手順を実行します:

1. XR ヘッドセット（Apple Vision Pro や PICO4 Ultra Enterprise など）を装着します

2. 対応する Wi-Fi ホットスポットに接続します

3. 頭部カメラで WebRTC を有効にしている場合（`cam_config_server.yaml → head_camera → enable_webrtc: true`）のみ、この手順を実行します。そうでない場合は手順 4 に進んでください。ブラウザ（Safari や PICO Browser など）を開き、次の URL にアクセスします: https://192.168.123.164:60001

   > **注1**: この IP は teleimager 画像サービスを起動している PC2 デバイスの IP です。

   > **注2**: 手順 4 と同様の警告が表示される場合があります。`Advanced` ボタンをクリックし、続いて `Proceed to ip (unsafe)` ボタンをクリックして、非セキュアな方法で WebRTC 画像サーバーに接続してください。接続後、左上の `start` ボタンをクリックし、頭部カメラの映像がプレビューできれば成功です。
   >
   > <p align="center">
   >   <a href="https://oss-global-cdn.unitree.com/static/777f9c6f42d74eb2a6438d1509a73025_2475x1574.jpg">
   >     <img src="https://oss-global-cdn.unitree.com/static/777f9c6f42d74eb2a6438d1509a73025_2475x1574.jpg" alt="webrtc_unsafe" style="width: 50%;">
   >   </a>
   > </p>
   >
   > **注3**: この手順には二つの目的があります。一つは頭部カメラサービスが正常かどうかの確認、もう一つは `webrtc` 自己署名証明書の手動信頼です。同じデバイス・同じ自己署名証明書の条件でこの手順を一度実行すれば、次回起動時はスキップできます。

4. ブラウザ（Safari や PICO Browser など）を開き、次の URL にアクセスします: https://192.168.123.2:8012/?ws=wss://192.168.123.2:8012

   > **注1**: この IP は **ホスト** の IP アドレスと一致させる必要があります（`ifconfig` などで確認）。

   > **注2**: PICO で websocket 接続を確立できない場合は、`https://vuer.ai?ws=wss://192.168.123.2:8012` を使用してください。

   > **注3**: 警告ページが表示される場合があります。`Advanced` ボタンをクリックし、続いて `Proceed to ip (unsafe)` ボタンをクリックしてください。

   <p align="center">
     <a href="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png">
       <img src="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png" alt="vuer_unsafe" style="width: 50%;">
     </a>
   </p>

5. `Vuer` ウェブ画面に入ったら、**`Virtual Reality`** ボタンをクリックします。以降のすべてのダイアログを許可した後、VR セッションを開始します。画面は以下の通りです:

   <p align="center">
     <a href="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png">
       <img src="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png" alt="Vuer UI" style="width: 75%;">
     </a>
   </p>

6. このとき、XR ヘッドセット内にロボットの一人称視点が表示されます。同時に、ターミナルに接続確立の情報が表示されます:

   ```bash
   websocket is connected. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
   default socket worker is up, adding clientEvents
   Uplink task running. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
   ```

7. 次に、実機展開時に初期姿勢の差が大きすぎてロボットが大きく揺れるのを避けるため、腕を**ロボットの初期姿勢**に近い姿勢に合わせます。

   ロボットの初期姿勢は以下の通りです:

   <p align="center">
     <a href="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png">
       <img src="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png" alt="初期姿勢" style="width: 25%;">
     </a>
   </p>

8. 最後に、ターミナルで **r** キーを押すと遠隔操作が正式に開始されます。これでロボットのアーム（および多指ハンド）を遠隔制御できます。

9. 遠隔操作中に **s** キーを押すとデータ記録を開始、再度 **s** キーを押すと記録を停止・保存します（この操作は繰り返し可能）。

   データ記録の様子:

   <p align="center">
     <a href="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png">
       <img src="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png" alt="記録プロセス" style="width: 75%;">
     </a>
   </p>

> **注1**: 記録データはデフォルトで `xr_teleoperate/teleop/utils/data` に保存されます。データの使用方法はこちらのリポジトリを参照してください: [unitree_IL_lerobot](https://github.com/unitreerobotics/unitree_IL_lerobot/tree/main?tab=readme-ov-file#data-collection-and-conversion)。
>
> **注2**: データ記録時はディスクの空き容量に注意してください。
>
> **注3**: v1.4 以降のバージョンでは、「record image」ウィンドウは廃止されました。

## 2.3 🔚 終了

プログラムを終了するには、ターミナルで **q** キーを押します。



# 3. 🤖 実機展開

実機展開の手順はシミュレーション展開とほぼ同じです。以下では主な相違点を説明します。

## 3.1 🖼️ 画像サービス

シミュレーション環境では画像サービスが自動的に有効化されます。実機展開時は、使用するカメラハードウェアに合わせて手動で画像サービスを起動する必要があります。手順は以下の通りです:

1. Unitree ロボット（G1/H1/H1_2 など）の**開発用計算ユニット PC2** に画像サービスプログラムをインストールします。

```bash
# SSH で PC2 にログインし、画像サービスプログラムのリポジトリをダウンロード
(base) unitree@PC2:~$ cd ~
(base) unitree@PC2:~$ git clone https://github.com/silencht/teleimager
# teleimager リポジトリの README（https://github.com/silencht/teleimager/blob/main/README.md）に従って環境を設定
```

2. **ローカルホスト**で以下のコマンドを実行します:

```bash
# 1.1 節で設定した key.pem と cert.pem（ローカルホストの xr_teleoperate/teleop/televuer 配下）を PC2 の対応パスにコピー
# これらの2ファイルは teleimager が WebRTC サービスを起動する際に必要です
(tv) unitree@Host:~$ scp ~/xr_teleoperate/teleop/televuer/key.pem ~/xr_teleoperate/teleop/televuer/cert.pem unitree@192.168.123.164:~/teleimager
# teleimager リポジトリの README に従い、PC2 で証明書パスを設定。例:
(teleimager) unitree@PC2:~$ cd teleimager
(teleimager) unitree@PC2:~$ mkdir -p ~/.config/xr_teleoperate/
(teleimager) unitree@PC2:~/teleimager$ cp cert.pem key.pem ~/.config/xr_teleoperate/
```

3. **開発用計算ユニット PC2** で teleimager ドキュメントに従って `cam_config_server.yaml` を設定し、画像サービスプログラムを起動します。

```bash
(teleimager) unitree@PC2:~/image_server$ python -m teleimager.image_server
# 次のコマンドでも同じ動作になります
(teleimager) unitree@PC2:~/image_server$ teleimager-server
```

4. **ローカルホスト**で以下のコマンドを実行して画像を購読します:

```bash
(tv) unitree@Host:~$ cd ~/xr_teleoperate/teleop/teleimager/src
(tv) unitree@Host:~/xr_teleoperate/teleop/teleimager/src$ python -m teleimager.image_client --host 192.168.123.164
# WebRTC 画像ストリームを設定している場合は、ブラウザで https://192.168.123.164:60001 を開き、Start ボタンをクリックしてテストできます
```



## 3.2 ✋ Inspire ハンドサービス（オプション）

> **注1**: 選択したロボット構成で Inspire 系多指ハンドを使用しない場合は、本節を無視してください。
>
> **注2**: G1 ロボット構成で [Inspire DFX 多指ハンド](https://support.unitree.com/home/zh/G1_developer/inspire_dfx_dexterous_hand) を使用する場合は、関連 issue [#46](https://github.com/unitreerobotics/xr_teleoperate/issues/46) を参照してください。
>
> **注3**: [Inspire FTP 多指ハンド](https://support.unitree.com/home/zh/G1_developer/inspire_ftp_dexterity_hand) を使用する場合は、関連 issue [#48](https://github.com/unitreerobotics/xr_teleoperate/issues/48) を参照してください。現在 FTP 多指ハンドに対応済みです。`--ee` パラメータを参照してください。

まず、[こちらのリンク: DFX_inspire_service](https://github.com/unitreerobotics/DFX_inspire_service) から多指ハンド制御インターフェースプログラムをクローンし、Unitree ロボットの **PC2** にコピーします。

Unitree ロボットの **PC2** で以下のコマンドを実行します:

```bash
unitree@PC2:~$ sudo apt install libboost-all-dev libspdlog-dev
# プロジェクトをビルド
unitree@PC2:~$ cd DFX_inspire_service && mkdir build && cd build
unitree@PC2:~/DFX_inspire_service/build$ cmake ..
unitree@PC2:~/DFX_inspire_service/build$ make -j6

# （unitree g1 の場合）ターミナル 1.
unitree@PC2:~/DFX_inspire_service/build$ sudo ./inspire_g1
# または（unitree h1 の場合）ターミナル 1.
unitree@PC2:~/DFX_inspire_service/build$ sudo ./inspire_h1 -s /dev/ttyUSB0

# ターミナル 2. サンプルを実行
unitree@PC2:~/DFX_inspire_service/build$ ./hand_example
```

両手が連続して開閉すれば成功です。成功したら、ターミナル 2 の `./hand_example` プログラムを終了してください。

## 3.3 ✋ BrainCo ハンドサービス（オプション）

[リポジトリのドキュメント](https://github.com/unitreerobotics/brainco_hand_service) を参照してください。

## 3.4 ✋ Unitree Dex1_1 サービス（オプション）

[リポジトリのドキュメント](https://github.com/unitreerobotics/dex1_1_service) を参照してください。

内部配線の Dex1 グリッパーを搭載した G1-29 では、`--arm G1_29 --ee dex1_internal` を使用してください。このモードでは、G1 の低レベルコマンドにあるモーター番号 31 と 33 を使用して左右のグリッパーをそれぞれ制御するため、外部 Dex1 サービスを起動する必要はありません。`rt/arm_sdk` 経由で内部配線のグリッパーを制御できるかどうかはまだ検証されていないため、現在は `--motion` と同時に使用できません。

## 3.5 🚀 遠隔操作の起動

>  ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
>  1. 潜在的な危険を防ぐため、すべての人はロボットから安全な距離を保ってください！
>  2. 本プログラムを実行する前に、[公式ドキュメント](https://support.unitree.com/home/zh/Teleoperation) を少なくとも一度は必ずお読みください。
>  3. **運動制御**モードで遠隔操作を行う場合は、事前に [R3 リモコン](https://www.unitree.com/cn/R3) でロボットを主運動制御モードにしておいてください。
>  5. **運動制御**モード（`--motion`）を有効にした場合:
>     - 右コントローラーの `A` ボタンは遠隔操作の**終了**ボタン
>     - 左右コントローラーの二つのスティックボタンを同時に押すとソフト非常停止となり、ロボットは運動制御プログラムを終了してダンピングモードに入ります（必要な場合のみ使用してください）
>     - 左コントローラーのスティックでロボットの前後左右移動を制御（最大制御速度はプログラム内で制限済み）
>     - 右コントローラーのスティックでロボットの旋回を制御（最大制御速度はプログラム内で制限済み）

シミュレーション展開とほぼ同じですが、上記の警告事項に注意してください。

## 3.6 🔚 終了

>  ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
>  ロボットの損傷を避けるため、ロボットのアームを初期姿勢付近の適切な位置に配置してから **q** を押して終了することを推奨します。
>
>  デバッグモード時: 終了キーを押すと、ロボットの両腕は5秒以内にロボットの初期姿勢に戻り、その後制御を終了します。
>
>  運動制御モード時: 終了キーを押すと、ロボットの両腕は5秒以内にロボットの運動制御姿勢に戻り、その後制御を終了します。

シミュレーション展開とほぼ同じですが、上記の警告事項に注意してください。



# 4. 🗺️ コードベース概要

```
xr_teleoperate/
│
├── assets                    [ロボット URDF 関連ファイルを格納]
│
├── teleop
│   ├── teleimager            [多機能に対応した新しい画像サービスライブラリ]
│   │
│   ├── televuer
│   │      ├── src/televuer
│   │         ├── television.py       [Vuer を用いて XR デバイスから頭部・手首・手/コントローラーのデータを取得]
│   │         ├── tv_wrapper.py       [取得データの後処理]
│   │      ├── test
│   │         ├── _test_television.py [television.py のテストプログラム]
│   │         ├── _test_tv_wrapper.py [tv_wrapper.py のテストプログラム]
│   │
│   ├── robot_control
│   │      ├── src/dex-retargeting [多指ハンドリターゲティングアルゴリズムライブラリ]
│   │      ├── robot_arm_ik.py     [アームの逆運動学]
│   │      ├── robot_arm.py        [両腕関節を制御し、その他の部分をロック]
│   │      ├── hand_retargeting.py [多指ハンドリターゲティングアルゴリズムのラッパー]
│   │      ├── robot_hand_inspire.py  [Inspire 多指ハンドを制御]
│   │      ├── robot_hand_unitree.py  [Unitree 多指ハンドを制御]
│   │
│   ├── utils
│   │      ├── episode_writer.py          [模倣学習用のデータ記録に使用]
│   │      ├── weighted_moving_filter.py  [関節データのフィルタリング用フィルタ]
│   │      ├── rerun_visualizer.py        [記録データの可視化に使用]
│   │      ├── ipc.py                     [エージェントプログラムとのプロセス間通信に使用]
│   │      ├── motion_switcher.py         [運動制御状態の切替に使用]
│   │      ├── sim_state_topic.py         [シミュレーション展開に使用]
│   │
│   └── teleop_hand_and_arm.py    [遠隔操作の起動実行コード]
```



# 5. 🛠️ ハードウェア

[ハードウェアドキュメント](Device.md) を参照してください。

# 6. 🙏 謝辞

このコードは以下のオープンソースコードを基に構築されています。各 LICENSE は以下の URL で確認してください:

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



# 7. 📝 引用

```
@misc{xr-teleoperate,
  author       = {{Unitree Robotics}},
  title        = {{XR-Teleoperate}: An Open-Source Teleoperation Framework and Data Collection Toolkit for Embodied Intelligence},
  howpublished = {\url{https://github.com/unitreerobotics/xr_teleoperate}},
  year         = {2024},
  note         = {Accessed: 2026-02}
}
```
