<div align="center">
  <h1 align="center">xr_teleoperate</h1>
  <a href="https://www.unitree.com/" target="_blank">
    <img src="https://www.unitree.com/images/0079f8938336436e955ea3a98c4e1e59.svg" alt="Unitree LOGO" width="15%">
  </a>
  <p align="center">
    <a href="README.md"> English </a> | <a href="README_zh-CN.md">中文</a> | <a>日本語</a>
  </p>
  <p align="center">
    <a href="https://github.com/unitreerobotics/xr_teleoperate/wiki">WiKi</a>
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

# 🔖 更新内容

1. **Vuerライブラリをアップグレード**し、より多くのXRデバイスモードに対応しました。これに伴い、プロジェクト名を **`avp_teleoperate`** から **`xr_teleoperate`** に変更しました。従来の Apple Vision Pro に加え、**Meta Quest 3（コントローラー対応）** や **PICO 4 Ultra Enterprise（コントローラー対応）** にも対応しています。
2. 一部の機能を**モジュール化**し、Gitサブモジュール（`git submodule`）を用いて管理・読み込みを行うことで、コード構造の明確化と保守性を向上させました。
3. **ヘッドレスモード**、**運用モード**、**シミュレーションモード**を新たに追加し、起動パラメータの設定を最適化しました（第2.2節参照）。**シミュレーションモード**により、環境構成の検証やハードウェア故障の切り分けが容易になります。
4. デフォルトの手指マッピングアルゴリズムを Vector から **DexPilot** に変更し、指先のつまみ動作の精度と操作性を向上させました。
5. その他、さまざまな最適化を実施しました。



# 0. 📖 イントロダクション

このリポジトリでは、**XR（拡張現実）デバイス**（Apple Vision Pro、PICO 4 Ultra Enterprise、Meta Quest 3など）を使用して**Unitreeヒューマノイドロボット**の**遠隔操作**を実装しています。

必要なデバイスと配線図は以下の通りです。

<p align="center">
  <a href="https://oss-global-cdn.unitree.com/static/3f75e91e41694ed28c29bcad22954d1d_5990x4050.png">
    <img src="https://oss-global-cdn.unitree.com/static/3f75e91e41694ed28c29bcad22954d1d_5990x4050.png" alt="システム構成図" style="width: 100%;">
  </a>
</p>


このリポジトリで現在サポートされているデバイス:

<table>
  <tr>
    <th align="center">🤖 ロボット</th>
    <th align="center">⚪ ステータス</th>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/g1" target="_blank">G1 (29 DoF)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/g1" target="_blank">G1 (23 DoF)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/h1" target="_blank">H1 (4自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/h1" target="_blank">H1_2 (7自由度アーム)</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/Dex1-1" target="_blank">Dex1‑1グリッパー</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.unitree.com/cn/Dex3-1" target="_blank">Dex3‑1多指ハンド</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"><a href="https://support.unitree.com/home/zh/G1_developer/inspire_dfx_dexterous_hand" target="_blank">Inspire多指ハンド</a></td>
    <td align="center">✅ 実装済み</td>
  </tr>
  <tr>
    <td align="center"> ··· </td>
    <td align="center"> ··· </td>
  </tr>
</table>


# 1. 📦 インストール

Ubuntu 20.04と22.04でテスト済みです。他のOSでは設定が異なる場合があります。本ドキュメントでは、主に通常モードについて説明します。

詳細は[公式ドキュメント](https://support.unitree.com/home/zh/Teleoperation)と[OpenTeleVision](https://github.com/OpenTeleVision/TeleVision)を参照してください。

## 1.0 ⚡ [pixi](https://pixi.sh) によるクイックインストール（推奨）

このリポジトリには `pixi.toml` と `pyproject.toml` が含まれているため、[pixi](https://pixi.sh) を使えば1つのコマンドで環境全体をセットアップできます。conda-forge の C++ ライブラリ（`pinocchio`、`casadi`、`numpy`、`cyclonedds`）とサブモジュール（`teleimager`、`televuer`、`dex-retargeting`）を自動で解決します。`linux-64` と `linux-aarch64`（ロボット内の Jetson など）に対応しています。

```bash
# pixi のインストール（https://pixi.sh 参照）: curl -fsSL https://pixi.sh/install.sh | bash
git clone https://github.com/unitreerobotics/xr_teleoperate.git
cd xr_teleoperate
git submodule update --init --depth 1        # パス依存関係にサブモジュールのツリーが必要
pixi install                                 # 環境の作成: conda ライブラリ + 編集可能なサブモジュール
pixi shell                                   # 環境に入り、通常通り teleop を実行
```

> **`unitree_sdk2py`（ロボット通信）。** `linux-64` では pixi が git から自動的に取得・インストールします。`cyclonedds==0.10.2` を固定しており、`linux-aarch64` 向けのホイールがないため、**Jetson（aarch64）** ではデバイス上で pixi が提供する `cyclonedds` C ライブラリに対してビルドする必要があります：
> ```bash
> # Jetson 上の `pixi shell` 内で実行:
> export CYCLONEDDS_HOME="$CONDA_PREFIX"
> pip install --no-build-isolation "git+https://github.com/unitreerobotics/unitree_sdk2_python.git"
> ```
>
> pixi の代わりに手動で conda をセットアップする場合は、セクション 1.1、1.2 と 1.3 の手順（`unitree_sdk2_python` の手動インストールを含む）に従ってください。

## 1.1 📥 Conda 環境

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

# Install dex-retargeting submodule
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ cd ../robot_control/dex-retargeting/
(tv) unitree@Host:~/xr_teleoperate/teleop/robot_control/dex-retargeting$ pip install -e .
# Install this repo (the `teleop` package) and its remaining dependencies
(tv) unitree@Host:~/xr_teleoperate/teleop/robot_control/dex-retargeting$ cd ../../../
(tv) unitree@Host:~/xr_teleoperate$ pip install -e .
```

## 1.2 🔐 SSL 証明書の設定（televuer）
> SSL 証明書の設定は XR デバイスの接続に必要です。pixi を使用した場合も手動 conda の場合も同様です。

XR デバイスは HTTPS / WebRTC でホストに接続するため、TLS 証明書が必要です。
`teleop/televuer/` ディレクトリで以下のコマンドを実行してください（pixi を使用した場合は `pixi shell` の中で実行）。

```bash
# Pico / Quest XR デバイスの場合
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem
```

```bash
# Apple Vision Pro の場合
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out rootCA.key 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -x509 -new -nodes -key rootCA.key -sha256 -days 365 -out rootCA.pem -subj "/CN=xr-teleoperate"
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl genrsa -out key.pem 2048
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl req -new -key key.pem -out server.csr -subj "/CN=localhost"
# server_ext.cnf を作成（IP.2 はホストの IP アドレスに合わせてください — ifconfig で確認）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ vim server_ext.cnf
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
IP.1 = 192.168.123.164
IP.2 = 192.168.123.2
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ openssl x509 -req -in server.csr -CA rootCA.pem -CAkey rootCA.key -CAcreateserial -out cert.pem -days 365 -sha256 -extfile server_ext.cnf
# rootCA.pem を AirDrop で Apple Vision Pro に転送してインストール

# ファイアウォールの有効化
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ sudo ufw allow 8012

# 証明書パスの設定 — どちらか一方を選択
# 2.1 ユーザー設定ディレクトリ（任意）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ mkdir -p ~/.config/xr_teleoperate/
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ cp cert.pem key.pem ~/.config/xr_teleoperate/
# 2.2 環境変数（任意）
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_CERT="$HOME/xr_teleoperate/teleop/televuer/cert.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ echo 'export XR_TELEOP_KEY="$HOME/xr_teleoperate/teleop/televuer/key.pem"' >> ~/.bashrc
(tv) unitree@Host:~/xr_teleoperate/teleop/televuer$ source ~/.bashrc
```

## 1.3 🕹️ unitree_sdk2_python

```bash
# ロボット通信用ライブラリインストール
(tv) unitree@Host:~$ git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
(tv) unitree@Host:~$ cd unitree_sdk2_python
(tv) unitree@Host:~/unitree_sdk2_python$ pip install -e .
```

> **注1**: 元のh1_2ブランチのunitree_dds_wrapperは暫定版でした。現在は公式Python制御ライブラリunitree_sdk2_pythonに移行済みです。
>
> **注2**: コマンド前の識別子は「どのデバイスでどのディレクトリで実行するか」を示しています。
>
> Ubuntuの`~/.bashrc`デフォルト設定: `PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '`
>
> 例: `(tv) unitree@Host:~$ pip install meshcat`
>
> - `(tv)` conda環境`tv`を表示
> - `unitree@Host:~` ユーザー`unitree`が`Host`デバイスにログイン、カレントディレクトリは`$HOME`
> - `$` Bashシェル（非rootユーザー）
> - `pip install meshcat` は`Host`で実行するコマンド

# 2. 💻 シミュレーション環境

## 2.1 📥 環境設定

まずunitree_sim_isaaclabをインストールし、READMEに従って設定します。

G1(29 DoF)とDex3ハンド構成でシミュレーションを起動:

```bash
(base) unitree@Host:~$ conda activate unitree_sim_env
(unitree_sim_env) unitree@Host:~$ cd ~/unitree_sim_isaaclab
(unitree_sim_env) unitree@Host:~/unitree_sim_isaaclab$ python sim_main.py --device cpu --enable_cameras --task Isaac-PickPlace-Cylinder-G129-Dex3-Joint --enable_dex3_dds --robot_type g129
```

シミュレーション起動後、ウィンドウをクリックして有効化。ターミナルに`controller started, start main loop...`と表示されます。

シミュレーションGUI:

<p align="center"> <a href="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png"> <img src="https://oss-global-cdn.unitree.com/static/bea51ef618d748368bf59c60f4969a65_1749x1090.png" alt="シミュレーションUI" style="width: 75%;"> </a> </p>

## 2.2 🚀 起動

物理ロボットとシミュレーションの両方でXR制御をサポート。コマンドライン引数でモード選択:

- **基本制御パラメータ**

| ⚙️ パラメータ |                📜 説明                |                         🔘 オプション                         | 📌 デフォルト |
| :----------: | :----------------------------------: | :----------------------------------------------------------: | :----------: |
| `--xr-mode`  |           XR入力モード選択           | `hand` (**ハンドトラッキング**) `controller` (**コントローラートラッキング**) |    `hand`    |
|   `--arm`    | ロボットアームタイプ選択 (0. 📖 参照) |                 `G1_29` `G1_23` `H1_2` `H1`                  |   `G1_29`    |
|    `--ee`    |   エンドエフェクタ選択 (0. 📖 参照)   |                   `dex1` `dex3` `inspire1`                   |     none     |

- **モードフラグ**

|   ⚙️ フラグ   |                            📜 説明                            |
| :----------: | :----------------------------------------------------------: |
|  `--record`  | **データ記録有効化**: **r**押下で開始後、**s**でエピソード記録開始/停止。繰り返し可能 |
|  `--motion`  | **モーション制御有効化**: 遠隔操作中に独立したロボット制御を許可。<br />ハンドモードではR3リモコンで歩行、コントローラーモードではジョイスティックで歩行 |
| `--headless` |             GUIなしで実行（ヘッドレスPC2展開用）             |
|   `--sim`    |               **シミュレーションモード**有効化               |

G1(29 DoF) + Dex3でハンドトラッキング、シミュレーション、記録モードで起動:

```bash
(tv) unitree@Host:~$ cd ~/xr_teleoperate/teleop/
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --xr-mode=hand --arm=G1_29 --ee=dex3 --sim --record
# 簡略化（デフォルト適用）:
(tv) unitree@Host:~/xr_teleoperate/teleop/$ python teleop_hand_and_arm.py --ee=dex3 --sim --record
```

プログラム起動後、ターミナル表示:

<p align="center"> <a href="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png"> <img src="https://oss-global-cdn.unitree.com/static/735464d237214f6c9edf8c7db9847a0a_1874x1275.png" alt="ターミナル起動ログ" style="width: 75%;"> </a> </p>

次の手順:

1. XRヘッドセット（Apple Vision Pro、PICO4など）を装着

2. 対応するWi-Fiに接続

3. ブラウザ（SafariやPICO Browserなど）で以下にアクセス: `https://192.168.123.2:8012?ws=wss://192.168.123.2:8012`

   > **注1**: このIPは**Host**のIPと一致させる必要あり（`ifconfig`で確認）。
   > ​**​注2​**: 警告ページが表示される場合があります。[詳細設定]→[IPにアクセス（安全ではない）]を選択。

   <p align="center"> <a href="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png"> <img src="https://oss-global-cdn.unitree.com/static/cef18751ca6643b683bfbea35fed8e7c_1279x1002.png" alt="vuer_unsafe" style="width: 50%;"> </a> </p>

4. Vuerウェブで[Virtual Reality]をクリック。すべてのプロンプトを許可してVRセッションを開始。

   <p align="center"> <a href="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png"> <img src="https://oss-global-cdn.unitree.com/static/fdeee4e5197f416290d8fa9ecc0b28e6_2480x1286.png" alt="Vuer UI" style="width: 75%;"> </a> </p>

5. ヘッドセットにロボットの一人称視点が表示されます。ターミナルに接続情報が表示:

```bash
websocket is connected. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
default socket worker is up, adding clientEvents
Uplink task running. id:dbb8537d-a58c-4c57-b49d-cbb91bd25b90
```

6. 急な動きを防ぐため、ロボットの**初期姿勢**に腕を合わせる:

<p align="center"> <a href="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png"> <img src="https://oss-global-cdn.unitree.com/static/2522a83214744e7c8c425cc2679a84ec_670x867.png" alt="初期姿勢" style="width: 25%;"> </a> </p>

7. ターミナルで**r**を押して遠隔操作を開始。ロボットアームと多指ハンドを制御できます。

8. 遠隔操作中、**s**で記録開始、再度**s**で停止・保存。繰り返し可能。

<p align="center"> <a href="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png"> <img src="https://oss-global-cdn.unitree.com/static/f5b9b03df89e45ed8601b9a91adab37a_2397x1107.png" alt="記録プロセス" style="width: 75%;"> </a> </p>

> **注1**: 記録データはデフォルトで`xr_teleoperate/teleop/utils/data`に保存。unitree_IL_lerobotで使用方法を確認。
> **注2**: データ記録時はディスク容量に注意してください。

## 2.3 🔚 終了

ターミナル（または「record image」ウィンドウ）で**q**を押して終了。

# 3. 🤖 物理環境展開

物理環境展開の手順はシミュレーションと似ていますが、以下の点が異なります:

## 3.1 🖼️ 画像サービス

`xr_teleoperate/teleop/image_server`ディレクトリの`image_server.py`をUnitreeロボット(G1/H1/H1_2など)の**開発用計算ユニットPC2**にコピーし。

```bash
# 補足: scpコマンドでimage_server.pyをPC2に転送後、sshでPC2にリモートログインして実行可能
# 開発用計算ユニットPC2のIPが192.168.123.164の場合の転送手順:
# SSHでPC2にログインし、画像サーバー用フォルダ作成
(tv) unitree@Host:~$ ssh unitree@192.168.123.164 "mkdir -p ~/image_server"
# ローカルのimage_server.pyをPC2の~/image_serverディレクトリにコピー
(tv) unitree@Host:~$ scp ~/xr_teleoperate/teleop/image_server/image_server.py unitree@192.168.123.164:~/image_server/
```

**PC2**で以下を実行:

```bash
# 補足: 現在この画像転送プログラムは、OpenCVとRealsense SDKの2つの画像読み取り方法をサポート。`image_server.py`内の`ImageServer`クラスのコメントを参照し、カメラハードウェアに合わせて画像転送サービスを設定。
# UnitreeロボットPC2のターミナルで実行
unitree@PC2:~/image_server$ python image_server.py
# ターミナルに以下の出力が表示:
# {'fps': 30, 'head_camera_type': 'opencv', 'head_camera_image_shape': [480, 1280], 'head_camera_id_numbers': [0]}
# [Image Server] Head camera 0 resolution: 480.0 x 1280.0
# [Image Server] Image server has started, waiting for client connections...
```

画像サービス起動後、**Host**ターミナルで`image_client.py`を使用して通信テスト可能:

```bash
(tv) unitree@Host:~/xr_teleoperate/teleop/image_server$ python image_client.py
```

## 3.2 ✋ Inspireハンドサービス（オプション）

> **Note 1**: Skip this if your config does not use the Inspire hand.
> **Note 2**: For the G1 robot with [Inspire DFX hand](https://support.unitree.com/home/zh/G1_developer/inspire_dfx_dexterous_hand), see [issue #46](https://github.com/unitreerobotics/xr_teleoperate/issues/46).
> **Note 3**: For [Inspire FTP hand]((https://support.unitree.com/home/zh/G1_developer/inspire_ftp_dexterity_hand)), see  [issue #48](https://github.com/unitreerobotics/xr_teleoperate/issues/48).

多指ハンド開発を参照して関連環境を設定し、制御プログラムをコンパイル。このURLから多指ハンド制御インターフェースプログラムをダウンロードし、Unitreeロボットの**PC2**にコピー。

Unitreeロボットの**PC2**で以下を実行:

```bash
unitree@PC2:~$ sudo apt install libboost-all-dev libspdlog-dev
# プロジェクトビルド
unitree@PC2:~$ cd h1_inspire_service & mkdir build & cd build
unitree@PC2:~/h1_inspire_service/build$ cmake .. -DCMAKE_BUILD_TYPE=Release
unitree@PC2:~/h1_inspire_service/build$ make
# ターミナル1. h1 inspireハンドサービス実行
unitree@PC2:~/h1_inspire_service/build$ sudo ./inspire_hand -s /dev/ttyUSB0
# ターミナル2. サンプル実行
unitree@PC2:~/h1_inspire_service/build$ ./h1_hand_example
```

両手が連続的に開閉すれば成功。成功後、ターミナル2の`./h1_hand_example`プログラムを終了。

## 3.3 🚀 起動

> ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
> 1. すべての人はロボットから安全な距離を保ち、潜在的な危険を防止してください！
> 2. このプログラムを実行する前に、少なくとも一度は公式ドキュメントをお読みください。
> 3. `--motion`なしの場合、ロボットがデバッグモード（L2+R2）に入り、モーション制御プログラムが停止していることを確認してください。これにより潜在的なコマンド競合問題を回避できます。
> 4. モーションモード（`--motion`あり）を使用する場合、ロボットが制御モード（R3リモコン経由）にあることを確認。
> 5. モーションモード時:
>    - 右コントローラー**A** = 遠隔操作終了
>    - 両ジョイスティック押下 = ソフト非常停止（ダンピングモードに切替）
>    - 左ジョイスティック = 移動方向;
>    - 右ジョイスティック = 旋回;
>    - 最大速度はコード内で制限。

シミュレーションと同じですが、上記の安全警告に従ってください。

## 3.4 🔚 終了

> ![Warning](https://img.shields.io/badge/Warning-Important-red)
>
> ロボット損傷を防ぐため、終了前にロボットの腕を初期姿勢に近づけることを推奨。
>
> - **デバッグモード**: 終了キー押下後、両腕は5秒以内にロボットの**初期姿勢**に戻り、制御終了。
> - **モーションモード**: 終了キー押下後、両腕は5秒以内にロボットの**モーション制御姿勢**に戻り、制御終了。

シミュレーションと同じですが、上記の安全警告に従ってください。

# 4. 🗺️ コード構成

```
xr_teleoperate/
│
├── assets                    [ロボットURDF関連ファイル格納]
│
├── hardware                  [3Dプリントハードウェアモジュール]
│
├── teleop
│   ├── image_server
│   │     ├── image_client.py      [ロボット画像サーバーから画像データを受信]
│   │     ├── image_server.py      [カメラから画像をキャプチャしネットワーク送信（ロボットの開発用計算ユニットPC2で実行）]
│   │
│   ├── televuer
│   │      ├── src/televuer
│   │         ├── television.py       [XRデバイスの頭部、手首、手・コントローラーのデータを取得]
│   │         ├── tv_wrapper.py       [取得データの後処理]
│   │      ├── test
│   │         ├── _test_television.py [television.pyのテスト]
│   │         ├── _test_tv_wrapper.py [tv_wrapper.pyのテスト]
│   │
│   ├── robot_control
│   │      ├── src/dex-retargeting [多指ハンドリターゲティングアルゴリズムライブラリ]
│   │      ├── robot_arm_ik.py     [アームの逆運動学]
│   │      ├── robot_arm.py        [両腕関節を制御し他をロック]
│   │      ├── hand_retargeting.py [多指ハンドリターゲティングアルゴリズムラッパー]
│   │      ├── robot_hand_inspire.py  [inspireハンド関節を制御]
│   │      ├── robot_hand_unitree.py  [unitreeハンド関節を制御]
│   │
│   ├── utils
│   │      ├── episode_writer.py          [模倣学習用データ記録]
│   │      ├── weighted_moving_filter.py  [関節データのフィルタリング]
│   │      ├── rerun_visualizer.py        [記録中のデータ可視化]
│   │
│   └── teleop_hand_and_arm.py    [遠隔操作起動実行コード]
```

# 5. 🛠️ ハードウェア

## 5.1 📋 部品リスト

|          アイテム          | 数量 |                            リンク                            |                             備考                             |
| :------------------------: | :--: | :----------------------------------------------------------: | :----------------------------------------------------------: |
| **ヒューマノイドロボット** |  1   |                   https://www.unitree.com                    |                    開発用計算ユニット付属                    |
|       **XRデバイス**       |  1   | https://www.apple.com/apple-vision-pro/ https://www.meta.com/quest/quest-3 https://www.picoxr.com/products/pico4-ultra-enterprise |                                                              |
|        **ルーター**        |  1   |                                                              |   **デフォルトモード**で必要; **ワイヤレスモード**では不要   |
|       **ユーザーPC**       |  1   |                                                              | **シミュレーションモード**では、公式推奨ハードウェアリソースを使用。 |
|  **ヘッドステレオカメラ**  |  1   |    [参考] http://e.tb.cn/h.TaZxgkpfWkNCakg?tk=KKz03Kyu04u    |                      ロボット頭部視点用                      |
|  **ヘッドカメラマウント**  |  1   | https://github.com/unitreerobotics/xr_teleoperate/blob/g1/hardware/head_stereo_camera_mount.STEP |                ヘッドステレオカメラ取り付け用                |
| Intel RealSense D405カメラ |  2   |      https://www.intelrealsense.com/depth-camera-d405/       |                            手首用                            |
|     手首リングマウント     |  2   | https://github.com/unitreerobotics/xr_teleoperate/blob/g1/hardware/wrist_ring_mount.STEP |                   手首カメラマウントと併用                   |
|     左手首D405マウント     |  1   | https://github.com/unitreerobotics/xr_teleoperate/blob/g1/hardware/left_wrist_D405_camera_mount.STEP |             左手首RealSense D405カメラ取り付け用             |
|     右手首D405マウント     |  1   | https://github.com/unitreerobotics/xr_teleoperate/blob/g1/hardware/right_wrist_D405_camera_mount.STEP |             右手首RealSense D405カメラ取り付け用             |
|       M3-1六角ナット       |  4   |                [参考] https://a.co/d/1opqtOr                 |                          手首固定用                          |
|         M3x12ネジ          |  4   |              [参考] https://amzn.asia/d/aU9NHSf              |                          手首固定用                          |
|          M3x6ネジ          |  4   |              [参考] https://amzn.asia/d/0nEz5dJ              |                          手首固定用                          |
|       **M4x14ネジ**        |  2   |              [参考] https://amzn.asia/d/cfta55x              |                          頭部固定用                          |
|      **M2x4自攻ネジ**      |  4   |              [参考] https://amzn.asia/d/1msRa5B              |                          頭部固定用                          |

>  注: 太字のアイテムは遠隔操作タスクに必須の設備、その他はデータセット記録用のオプション設備。

## 5.2 🔨 取り付け図

<table> <tr> <th align="center">アイテム</th> <th align="center" colspan="2">シミュレーション</th> <th align="center" colspan="2">実機</th> </tr> <tr> <td align="center">頭部</td> <td align="center"> <p align="center"> <img src="./img/head_camera_mount.png" alt="頭部" width="100%"> <figcaption>頭部マウント</figcaption> </p> </td> <td align="center"> <p align="center"> <img src="./img/head_camera_mount_install.png" alt="頭部" width="80%"> <figcaption>取り付け側面図</figcaption> </p> </td> <td align="center" colspan="2"> <p align="center"> <img src="./img/real_head.jpg" alt="頭部" width="20%"> <figcaption>取り付け正面図</figcaption> </p> </td> </tr> <tr> <td align="center">手首</td> <td align="center" colspan="2"> <p align="center"> <img src="./img/wrist_and_ring_mount.png" alt="手首" width="100%"> <figcaption>手首リングとカメラマウント</figcaption> </p> </td> <td align="center"> <p align="center"> <img src="./img/real_left_hand.jpg" alt="手首" width="50%"> <figcaption>左手取り付け図</figcaption> </p> </td> <td align="center"> <p align="center"> <img src="./img/real_right_hand.jpg" alt="手首" width="50%"> <figcaption>右手取り付け図</figcaption> </p> </td> </tr> </table>

> 注: 手首リングマウントは、ロボットの手首の継ぎ目に合わせて取り付け（画像の赤丸部分）。

# 6. 🙏 謝辞

このコードは以下のオープンソースコードを基にしています。各LICENSEはURLで確認してください:

1. https://github.com/OpenTeleVision/TeleVision
2. https://github.com/dexsuite/dex-retargeting
3. https://github.com/vuer-ai/vuer
4. https://github.com/stack-of-tasks/pinocchio
5. https://github.com/casadi/casadi
6. https://github.com/meshcat-dev/meshcat-python
7. https://github.com/zeromq/pyzmq
8. https://github.com/Dingry/BunnyVisionPro
9. https://github.com/unitreerobotics/unitree_sdk2_python
