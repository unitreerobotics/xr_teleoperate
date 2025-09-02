import os
import time
import cv2
import numpy as np

def _third_camera(
    device,
    image_shape,                 # (H, W, 3)
    out_array,                   # shared np.ndarray(dtype=uint8, shape=(H,W,3))
    fps,
    stop_event,
    logger,
    *,
    warmup_frames=5,
    prefer_mjpg=True,
    read_fail_threshold=30,
    reopen_backoff_sec=0.5,
    set_buffer_size=True,
    resize_if_mismatch=True,
):
    H, W = image_shape[0], image_shape[1]

    assert out_array.shape[0] == H and out_array.shape[1] == W and out_array.shape[2] == 3, \
        f"out_array shape must be ({H},{W},3), got {out_array.shape}"
    assert out_array.dtype == np.uint8, "out_array dtype must be uint8"

    def _open_capture():
        if os.name != 'nt':
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(device)  # fallback
        else:
            cap = cv2.VideoCapture(device)      # Windows
        return cap

    cap = _open_capture()
    if not cap.isOpened():
        logger.error(f"[third camera] Failed to open device: {device}")
        return

    try:
        if prefer_mjpg:
            if not cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')):
                pass
        else:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))

        if set_buffer_size:
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        cap.set(cv2.CAP_PROP_FPS,          fps)

        act_W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        act_H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        act_FPS = float(cap.get(cv2.CAP_PROP_FPS)) or fps
        fourcc  = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_s = "".join([chr((fourcc >> 8*i) & 0xFF) for i in range(4)]) if fourcc != 0 else "unknown"

        logger.info(f"[third camera] requested {W}x{H}@{fps}, negotiated {act_W}x{act_H}@{act_FPS:.2f}, FOURCC={fourcc_s}")

        for _ in range(max(0, warmup_frames)):
            ret, _ = cap.read()
            if not ret:
                break

        interval = 1.0 / max(1.0, float(fps))
        next_t = time.perf_counter() + interval
        fail_cnt = 0

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                fail_cnt += 1
                if fail_cnt >= read_fail_threshold:
                    logger.warning(f"[third camera] read failed x{fail_cnt}, reopening ({device})")
                    cap.release()
                    time.sleep(reopen_backoff_sec)
                    cap = _open_capture()
                    if not cap.isOpened():
                        logger.error(f"[third camera] reopen failed: {device}")
                        time.sleep(reopen_backoff_sec)
                        continue
                    tried_mjpg = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    if not tried_mjpg:
                        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
                    cap.set(cv2.CAP_PROP_FPS,          fps)
                    if set_buffer_size:
                        try: cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        except Exception: pass

                    fail_cnt = 0
                else:
                    time.sleep(0.005)
                now = time.perf_counter()
                if now - next_t > 2*interval:
                    next_t = now + interval
                continue

            fail_cnt = 0

            if resize_if_mismatch and (frame.shape[1] != W or frame.shape[0] != H):
                frame = cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA)

            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.ndim == 3 and frame.shape[2] == 4:  # BGRA → BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            if frame.dtype != np.uint8:
                frame = np.clip(frame, 0, 255).astype(np.uint8)

            out_array[...] = frame

            now = time.perf_counter()
            if now < next_t:
                time.sleep(next_t - now)
                next_t += interval
            else:
                missed = int((now - next_t) // interval) + 1
                next_t += missed * interval
                if (now - next_t) > 2*interval:
                    next_t = now + interval

    except Exception as e:
        logger.exception(f"[third camera] unexpected error: {e}")
    finally:
        try:
            cap.release()
        except Exception:
            pass
        logger.info("[third camera] capture thread stopped.")