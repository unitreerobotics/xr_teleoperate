# 🚶 Locomotion: walking in both controller and hand mode

On a G1 running `--motion`, **locomotion is available from either input mode**. Both paths end
at the same call — `loco_wrapper.Move(vx, vy, vyaw)` — and both use the **same axis mapping**.
The only difference is where the three axes come from:

- **`--input-mode=controller`** — the thumbsticks, as before.
- **`--input-mode=hand`** — there are no thumbsticks, so the operator **double-nods** to flip
  into WALK mode and then steers by **displacing their arms**, which become the joystick.

```mermaid
flowchart LR
  subgraph CTRL["--input-mode=controller"]
    LS["Left thumbstick<br/>x / y"]
    RS["Right thumbstick<br/>x"]
    SP["Stick presses<br/>select walk / finger"]
  end

  subgraph HAND["--input-mode=hand"]
    ND["Double head-nod<br/>toggles WALK"]
    LW["Left wrist<br/>displacement"]
    RW["Right wrist<br/>displacement"]
  end

  LS --> MV
  RS --> MV
  SP -. gates .-> MV
  LW --> MV
  RW --> MV
  ND -. gates .-> LW
  ND -. gates .-> RW

  MV["loco_wrapper.Move(vx, vy, vyaw)"] --> FSM["G1 legs<br/>FSM 501 main control"]
```

## 🎯 Shared axis mapping

The hand-mode mapping was chosen to mirror the thumbsticks exactly, so muscle memory carries
across modes:

| Axis   | Meaning         | Controller mode              | Hand mode (WALK)                   |
| :----- | :-------------- | :--------------------------- | :--------------------------------- |
| `vx`   | forward / back  | left stick, vertical         | **left** arm forward / back        |
| `vy`   | strafe          | left stick, horizontal       | **left** arm left / right          |
| `vyaw` | turn            | right stick, horizontal      | **right** arm left / right         |

Controller values are scaled by `0.3`; hand values run through a deadzone and gain, then clamp
at `WALK_VMAX` (also `0.3` by default). Wrist poses are already in the arm-IK target frame
(robot basis: x = forward, y = left, z = up), so displacement maps straight onto the axes.

---

# 🕹️ Controller mode

Both modes coexist on the same sticks; a **stick press** selects which one is live. This is what
makes walking and grasping possible in one session with `--ee=inspire_dfx`.

```mermaid
stateDiagram-v2
    [*] --> Walk
    Walk --> Finger: right stick press
    Finger --> Walk: left stick press
    Walk --> Damp: both sticks pressed
    Finger --> Damp: both sticks pressed

    note right of Walk
      Legs follow the thumbsticks.
      Fingers held neutral.
      A button quits teleoperation.
    end note

    note right of Finger
      Move(0, 0, 0) - legs stop.
      Thumbsticks drive the fingers.
      A button drives the right thumb.
    end note
```

⚠️ **The A button is overloaded.** It quits teleoperation only in **walk** mode. In finger mode
it drives the right thumb away from the palm, so quitting requires a left-stick press first.

Pressing **both sticks together** is the soft e-stop and calls `Enter_Damp_Mode()`, regardless of
which mode is active.

---

# 🙆 Hand mode: nodding to switch states

With no thumbsticks available, hand mode needs a gesture that is **unambiguous** and does not
collide with ordinary manipulation. A *double downward head-nod* was chosen because a vertical
head motion is easy to perform deliberately and hard to perform by accident while looking around.

```mermaid
stateDiagram-v2
    [*] --> HandTrack
    HandTrack --> Walk: double nod
    Walk --> HandTrack: double nod

    note right of HandTrack
      Arms IK-track the operator.
      Fingers grasp normally.
      Legs held at Move(0, 0, 0).
    end note

    note right of Walk
      Arms FROZEN - they are the joystick.
      Fingers FROZEN at their last pose.
      Arm displacement drives the legs.
    end note
```

On entering WALK the controller captures the current wrist positions as the **joystick centre**,
so steering is measured relative to wherever your arms happened to be — there is no need to
return to a fixed neutral pose first.

Two freezes happen on entry, and both matter:

- **Arms freeze** at the last tracked IK solution (`frozen_sol_q`). Without this the robot's arms
  would flail as you waved yours around to steer.
- **Fingers freeze** at their last pose — the finger position arrays simply stop being updated.
  Without this, the steering motion would be retargeted into an unintended grasp.

## 🔍 How the nod is detected

The detector never looks at absolute head angle — only at *transient deviation from where your
head has recently been resting*. That way it works regardless of how you naturally hold your head.

```mermaid
flowchart TD
  A["Head pose 4x4<br/>rotation matrix"] --> B["signal = sign x R row col<br/>default row 1, col 2"]
  B --> C["Slow EMA baseline<br/>tau = NOD_BASELINE_TAU"]
  C --> D["deviation = baseline - signal"]
  D --> E{"deviation above<br/>NOD_ENTER?"}
  E -- yes --> F["Enter dip"]
  F --> G{"deviation below<br/>NOD_ENTER x NOD_EXIT_FRAC?"}
  G -- yes --> H["Release dip<br/>record timestamp"]
  H --> I{"NOD_COUNT dips<br/>within NOD_WINDOW_S?"}
  I -- yes --> J{"past refractory<br/>lockout?"}
  J -- yes --> K["FIRE - toggle mode"]
  K --> L["Clear dips<br/>start refractory"]
  I -- no --> M["Keep waiting<br/>old dips expire"]
```

Step by step:

1. **Signal.** One entry of the head rotation matrix — by default `R[1, 2]`, the vertical
   component of the head's fore-aft axis under OpenXR's Y-up convention. Nodding tilts that axis
   and moves the number; a left/right head *shake* is a yaw rotation and barely moves a vertical
   matrix entry, which is why looking around does not trigger it.
2. **Baseline.** A slow exponential moving average (default τ = 1.0 s) tracks your resting head
   pose, so a quick nod appears as a short-lived deviation rather than a permanent offset.
3. **Dip with hysteresis.** A dip *starts* when `deviation` exceeds `NOD_ENTER` (0.12) and only
   *completes* when it falls back below `NOD_ENTER × NOD_EXIT_FRAC` (0.06). The two different
   thresholds stop a signal hovering near the edge from rattling off dozens of dips.
4. **Counting.** The dip is recorded **on release**, not on entry. Dips older than
   `NOD_WINDOW_S` (3.0 s) are discarded, so the two nods must land inside a rolling window.
5. **Refractory lockout.** After firing, further toggles are suppressed for `NOD_REFRACTORY_S`
   (1.0 s) and the dip list is cleared, so one gesture cannot fire twice.

### ⏱️ What fires and what doesn't

```
signal
  │   ┌──┐    ┌──┐                    ┌──┐                 ┌──┐    ┌──┐
  │   │  │    │  │                    │  │                 │  │    │  │
──┴───┘  └────┘  └────────────────────┘  └─────────────────┘  └────┘  └──────
      nod 1    nod 2                  single nod           nod 1    nod 2
      └──── within 3.0 s ────┘                             └── within 3.0 s ──┘
              ✅ FIRE                     ❌ expires                ✅ FIRE
```

A lone nod never toggles anything — it simply ages out of the window. This is the behaviour
covered by the module's self-test, which feeds a synthetic signal through the detector and
asserts exactly two toggles:

```bash
python -m teleop.utils.hand_walk     # no robot, no XR headset required
```

### 🎚️ Tuning the nod

Every parameter is an environment variable, so the gesture can be calibrated on the gantry
without editing code. Run with `NOD_DEBUG=1` to print the live signal, baseline, deviation and
dip count each frame:

| Variable            | Default | Effect                                                        |
| :------------------ | :------ | :------------------------------------------------------------ |
| `NOD_COUNT`         | `2`     | Dips required to fire. `3` if double-nods trigger accidentally. |
| `NOD_WINDOW_S`      | `3.0`   | Rolling window the dips must land inside.                      |
| `NOD_ENTER`         | `0.12`  | Deviation to start a dip. Raise if it over-triggers.           |
| `NOD_EXIT_FRAC`     | `0.5`   | Release threshold as a fraction of `NOD_ENTER`.                |
| `NOD_BASELINE_TAU`  | `1.0`   | Baseline time constant, seconds.                               |
| `NOD_REFRACTORY_S`  | `1.0`   | Lockout after a fire.                                          |
| `NOD_SIGN`          | `1.0`   | Flip if nodding **down** registers as up.                      |
| `NOD_ROW` / `NOD_COL` | `1` / `2` | Which rotation-matrix cell to use, if your headset frame differs. |

> 💡 `NOD_WINDOW_S` was widened from 1.5 s to 3.0 s after on-robot testing — 1.5 s demanded an
> uncomfortably brisk double-nod.

### 🎚️ Tuning the steering

| Variable             | Default | Effect                                        |
| :------------------- | :------ | :-------------------------------------------- |
| `WALK_VMAX`          | `0.3`   | Velocity clamp on all three axes.             |
| `WALK_DEADZONE_M`    | `0.05`  | Displacement ignored around the centre, metres. |
| `WALK_GAIN_FWD`      | `1.5`   | Metres of displacement → `vx`.                 |
| `WALK_GAIN_STRAFE`   | `1.5`   | Metres of displacement → `vy`.                 |
| `WALK_GAIN_TURN`     | `2.0`   | Metres of displacement → `vyaw`.               |
| `WALK_SIGN_*`        | `1.0`   | Flip an axis that steers backwards.            |

`WALK_DEBUG=1` prints the live displacements and resulting velocities.

---

# 🛡️ Safety behaviour

| Condition                        | Response                                                          |
| :------------------------------- | :---------------------------------------------------------------- |
| XR tracking lost in hand mode    | `Move(0, 0, 0)` every frame — the robot never keeps walking on stale data. |
| Both sticks pressed (controller) | `Enter_Damp_Mode()` soft e-stop.                                   |
| DDS link dies                    | `LinkWatchdog` logs an explicit error instead of freezing silently. |
| Entering WALK (hand mode)        | Arms and fingers freeze, so steering cannot become a grasp.         |

⚠️ `LinkWatchdog` tracks **lowstate freshness only**. A motor in a PC-to-motor timeout still
reports through a healthy link and will not be caught here.

---

# ⚙️ Reaching the walkable state

None of the above works until the robot is in its walkable FSM state. On G1 **sw 1.5.3** the
SDK's `Start()` sets FSM 500, which this firmware silently ignores — it returns success while the
robot stays in 802 and refuses to walk. The walkable state is **501**, reached via
damp → stand → main-control:

```mermaid
sequenceDiagram
    participant W as LocoClientWrapper
    participant R as G1 sw 1.5.3

    W->>R: SetFsmId(1) damp
    Note over W: wait 1 s
    W->>R: SetFsmId(4) stand up
    Note over R: physical stand-up,<br/>several seconds
    loop up to 12 attempts
        W->>R: SetFsmId(501)
        W->>R: GetFsmId()
        Note over W: 501 is ignored until<br/>the stand-up completes
    end
    Note over W,R: confirmed at 501 - Move() now takes effect
```

The retry loop exists because the stand-up is a physical motion of variable duration, and
`SetFsmId(501)` is discarded until it finishes. Override the target with `G1_CTRL_FSM` if a
future firmware moves it.

> 💡 Only `Regular mode` (R1+X) is supported. `Running mode` (R2+A) is not.
