# 🔖 版本说明

## 🏷️ v1.6 (2026.7.29)

- 支持 **H2** 机器人
- 支持 **R1** 机器人（`R1_A5` 手臂5自由度、`R1_A7` 手臂7自由度）
- 支持 **BrainCo** 灵巧手手柄输入控制
- 默认采用**基于头部偏航（head-yaw）的手臂参考系**，使腕部目标相对于操作者的偏航朝向表达，同时忽略头部的俯仰与横滚（此前仅平移的行为仍然保留）

------

- 修复 Dex3 重定向（retargeting）bug
- 修复手柄输入模式下 Dex1 夹爪闭合 bug
- 修复非双目头部相机录制时的颜色格式（BGR）问题

## 🏷️ v1.5 (2025.12.29)

- 支持**仿真模式**
- 添加 cyclonedds 网卡名称参数
- 升级 teleimager 版本
- [将 IPC 迁移至 @ 虚拟地址](https://github.com/unitreerobotics/xr_teleoperate/commit/46603c5ff385da7a9de59fb4a4a5dca1de4d9133)
- [引入缓存机制以加速 URDF 加载](https://github.com/unitreerobotics/xr_teleoperate/commit/6cab654620735bfa347c1cd32a0d8c0c1e6ec343)

## 🏷️ v1.4 (2025.11.21)

- **图像服务器**变更为 [teleimager](https://github.com/silencht/teleimager)，具体请查看仓库README。

- 升级 [televuer](https://github.com/silencht/televuer)，具体请查看仓库README。

  > 新版本的 [teleimager](https://github.com/silencht/teleimager/commit/ab5018691943433c24af4c9a7f3ea0c9a6fbaf3c) + [televuer](https://github.com/silencht/televuer/releases/tag/v3.0) 支持通过 **webrtc** 传输头部相机图像
  >
  > 支持 pass-through, ego, immersive 三种模式：pass-through 为通透模式，直接通过 VR 相机查看现实世界来观察机器人；ego 是在通透模式的基础上，添加一个机器人视角的小窗；immersive 是完全沉浸机器人第一人称视角模式。

- 丰富**录制模式**下的任务信息传递参数，修复和完善 EpisodeWriter。

- 完善系统的**状态机信息**、IPC模式。

- 新增 **affinity CPU 亲和模式**，如果你不了解该模式，那么请无视它。

- 新增 **motion-switcher 功能**，无需遥控器即可自动进退 debug 模式。

- 支持 **inspire_FTP** 灵巧手

## 🏷️ v1.3 ( 2025.10.14)

- 添加 [![Unitree LOGO](https://camo.githubusercontent.com/ff307b29fe96a9b115434a450bb921c2a17d4aa108460008a88c58a67d68df4e/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f4769744875622d57696b692d3138313731373f6c6f676f3d676974687562)](https://github.com/unitreerobotics/xr_teleoperate/wiki) [![Unitree LOGO](https://camo.githubusercontent.com/6f5253a8776090a1f89fa7815e7543488a9ec200d153827b4bc7c3cb5e1c1555/68747470733a2f2f696d672e736869656c64732e696f2f62616467652f2d446973636f72642d3538363546323f7374796c653d666c6174266c6f676f3d446973636f7264266c6f676f436f6c6f723d7768697465)](https://discord.gg/ZwcVwxv5rq)

- 支持 **IPC 模式**，默认使用 SSHKeyboard 进行输入控制。  
- 合并 **H1_2** 机器人新增运动模式支持。  
- 合并 **G1_23** 机械臂新增运动模式支持。  

------

- 优化了数据记录功能。  
- 改进了仿真环境中的夹持器（gripper）使用体验。  

------

- 通过在控制器启动前初始化 IK，修复了启动时的抖动问题。  
- 修复了 SSHKeyboard 停止监听的 bug。  
- 修复了启动按钮逻辑错误。  
- 修复了仿真模式中的若干 bug。  

## 🏷️ v1.2 (2025.7.22)

1. 升级Dex1_1夹爪控制代码，匹配 [dex1_1 service](https://github.com/unitreerobotics/dex1_1_service) 驱动

## 🏷️ v1.1 (2025.7.18)

1. 末端执行器类型新增'brainco'，这是[强脑科技第二代灵巧手](https://www.brainco-hz.com/docs/revolimb-hand/)
2. 为避免与实机部署时发生冲突，将仿真模式下的 dds 通道的domain id修改为1
3. 修复默认频率过高的问题

## 🏷️ v1.0 (newvuer)(2025.7.8)

1. 升级 [Vuer](https://github.com/vuer-ai/vuer) 库至 v0.0.60 版本，XR设备支持模式扩展为**手部跟踪**和**控制器跟踪**两种。为更准确反映功能范围，项目由 **avp_teleoperate** 更名为 **xr_teleoperate**。

   测试设备包括： Apple Vision Pro，Meta Quest 3（含手柄） 与 PICO 4 Ultra Enterprise（含手柄）。

2. 对部分功能进行了**模块化**拆分，并通过 Git 子模块（git submodule）方式进行管理和加载，提升代码结构的清晰度与维护性。

3. 新增**无头**、**运控**及**仿真**模式，优化启动参数配置（详见第2.2节），提升使用便捷性。**仿真**模式的加入，方便了环境验证和硬件故障排查。

4. 将默认手部映射算法从 Vector 切换为 **DexPilot**，优化了指尖捏合的精度与交互体验。

5. 其他一些优化

## 🏷️ v0.5 (oldvuer) (2025.4.30)

1. 该版本曾经命名为 `avp_teleoperate`
2. 支持 'G1_29', 'G1_23', 'H1_2', 'H1' 机器人类型
3. 支持 'dex3', 'gripper', 'inspire1' 末端执行器类型
4. 仅支持 XR 设备的手部跟踪模式（ [Vuer](https://github.com/vuer-ai/vuer) 版本为 v0.0.32RC7），不支持控制器模式
5. 支持数据录制模式