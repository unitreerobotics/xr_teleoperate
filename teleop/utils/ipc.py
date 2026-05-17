import os
import zmq
import time
import threading
import logging_mp
logger_mp = logging_mp.getLogger(__name__)

"""
# Client → Server (Request)
1) tracking start / pause / resume
    {
        "reqid": unique id,
        "cmd": "CMD_START"
    }

2) exit
    {
        "reqid": unique id,
        "cmd": "CMD_STOP"
    }

3) start or stop (record toggle)
    {
        "reqid": unique id,
        "cmd": "CMD_RECORD_TOGGLE"
    }

# Server → Client (Reply)
1) if ok
    {
        "repid": same as reqid,
        "status": "ok",
        "msg": "ok"
    }
2) if error
    {
        "repid": same as reqid | 0 | 1,   # 0: no reqid provided, 1: internal error
        "status": "error",
        "msg": "reqid not provided" 
             | "cmd not provided" 
             | "cmd not supported: {cmd}" 
             | "internal error msg"
    }

# Heartbeat (PUB)
- Heartbeat Pub format:
    {
        "START": True | False,          # whether robot follow vr
        "STOP" : True | False,          # whether exit program
        "HOMING": True | False,         # whether arms are returning to default pose
        "PAUSED": True | False,         # whether tracking is paused at default pose
        "RECORD_RUNNING": True | False, # whether is recording
        "RECORD_READY": True | False,   # whether ready to record
    }
"""


class IPC_Server:
    """
    Inter - Process Communication Server:
    - Handle data via REP
    - Publish heartbeat via PUB, Heartbeat state is provided by external callback get_state()
    """
    # Mapping table for on_press keys
    cmd_map = {
        "CMD_START": "r",          # start / pause / resume tracking
        "CMD_STOP": "q",           # exit
        "CMD_RECORD_TOGGLE": "s",  # start & stop (toggle record)
    }

    def __init__(self, on_press=None, get_state=None, hb_fps=10.0):
        """
        Args:
            on_press  : callback(cmd:str), called for every command
            get_state : callback() -> dict, provides current heartbeat state
            hb_fps    : heartbeat publish frequency
        """
        if callable(on_press):
            self.on_press = on_press
        else:
            raise ValueError("[IPC_Server] on_press callback function must be provided")

        if callable(get_state):
            self.get_state = get_state
        else:
            raise ValueError("[IPC_Server] get_state callback function must be provided")
        self._hb_interval = 1.0 / float(hb_fps)
        self._running = True
        self._data_loop_thread = None
        self._hb_loop_thread = None

        self.ctx = zmq.Context.instance()
        self.rep_socket = self.ctx.socket(zmq.REP)
        self.rep_socket.bind("ipc://@xr_teleoperate_data.ipc")
        logger_mp.info("[IPC_Server] Listening to Data at ipc://@xr_teleoperate_data.ipc")

        # heartbeat IPC (PUB/SUB)
        self.pub_socket = self.ctx.socket(zmq.PUB)
        self.pub_socket.bind("ipc://@xr_teleoperate_hb.ipc")
        logger_mp.info("[IPC_Server] Publishing HeartBeat at ipc://@xr_teleoperate_hb.ipc")

    def _data_loop(self):
        """
        Listen for REQ/REP commands and optional info.
        """
        poller = zmq.Poller()
        poller.register(self.rep_socket, zmq.POLLIN)
        while self._running:
            try:
                socks = dict(poller.poll(20))
                if self.rep_socket in socks:
                    msg = self.rep_socket.recv_json()
                    reply = self._handle_message(msg)
                    try:
                        self.rep_socket.send_json(reply)
                    except Exception as e:
                        logger_mp.error(f"[IPC_Server] Failed to send reply: {e}")
                    finally:
                        logger_mp.debug(f"[IPC_Server] DATA recv: {msg} -> rep: {reply}")
            except zmq.error.ContextTerminated:
                break
            except Exception as e:
                logger_mp.error(f"[IPC_Server] Data loop exception: {e}")

    def _hb_loop(self):
        """Publish heartbeat periodically""" 
        while self._running:
            start_time = time.monotonic()
            try:
                state = dict(self.get_state() or {})
                self.pub_socket.send_json(state)
                logger_mp.debug(f"[IPC_Server] HB pub: {state}")
            except Exception as e:
                logger_mp.error(f"[IPC_Server] HeartBeat loop exception: {e}")
            elapsed = time.monotonic() - start_time
            if elapsed < self._hb_interval:
                time.sleep(self._hb_interval - elapsed)

    def _handle_message(self, msg: dict) -> dict:
        """Process message and return reply"""
        try:
            # validate reqid
            reqid = msg.get("reqid", None)
            if not reqid:
                return {"repid": 0, "status": "error", "msg": "reqid not provided"}

            # validate cmd
            cmd = msg.get("cmd", None)
            if not cmd:
                return {"repid": reqid, "status": "error", "msg": "cmd not provided"}

            # unsupported cmd
            if cmd not in self.cmd_map:
                return {"repid": reqid, "status": "error", "msg": f"cmd not supported: {cmd}"}
                    
            # supported cmd path
            self.on_press(self.cmd_map[cmd])
            return {"repid": reqid, "status": "ok", "msg": "ok"}

        except Exception as e:
            return {"repid": 1, "status": "error", "msg": str(e)}
        
    # ---------------------------
    # Public API
    # ---------------------------
    def start(self):
        """Start both data loop and heartbeat loop"""
        self._data_loop_thread = threading.Thread(target=self._data_loop, daemon=True)
        self._data_loop_thread.start()
        self._hb_loop_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_loop_thread.start()

    def stop(self):
        """Stop server"""
        self._running = False
        if self._data_loop_thread:
            self._data_loop_thread.join(timeout=1.0)
        if self._hb_loop_thread:
            self._hb_loop_thread.join(timeout=1.0)
        try:
            self.rep_socket.setsockopt(zmq.LINGER, 0)
            self.rep_socket.close()
        except Exception:
            pass
        try:
            self.pub_socket.setsockopt(zmq.LINGER, 0)
            self.pub_socket.close()
        except Exception:
            pass
        try:
            self.ctx.term()
        except Exception:
            pass


class IPC_Client:
    """
    Inter - Process Communication Client:
    - Send command via REQ
    - Subscribe heartbeat via SUB
    """
    def __init__(self, hb_fps=10.0):
        """hb_fps: heartbeat subscribe frequency, should match server side."""
        self.ctx = zmq.Context.instance()

        # heartbeat IPC (PUB/SUB)
        self._hb_running = True
        self._hb_last_time = 0           # timestamp of last heartbeat received
        self._hb_latest_state = {}       # latest heartbeat state
        self._hb_online = False          # whether heartbeat is online
        self._hb_interval = 1.0 / float(hb_fps)     # expected heartbeat interval
        self._hb_lock = threading.Lock()            # lock for heartbeat state
        self._hb_timeout = 5.0 * self._hb_interval  # timeout to consider offline

        self.sub_socket = self.ctx.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.RCVHWM, 1)
        self.sub_socket.connect("ipc://@xr_teleoperate_hb.ipc")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        logger_mp.info("[IPC_Client] Subscribed to HeartBeat at ipc://@xr_teleoperate_hb.ipc")

        self._hb_thread = threading.Thread(target=self._hb_loop, daemon=True)
        self._hb_thread.start()

        # data IPC (REQ/REP)
        self.req_socket = self.ctx.socket(zmq.REQ)
        self.req_socket.connect("ipc://@xr_teleoperate_data.ipc")
        logger_mp.info("[IPC_Client] Connected to Data at ipc://@xr_teleoperate_data.ipc")

    def _make_reqid(self) -> str:
        import uuid
        return str(uuid.uuid4())

    # ---------------------------
    # Heartbeat handling
    # ---------------------------
    def _hb_loop(self):
        consecutive = 0
        while self._hb_running:
            start_time = time.monotonic()
            try:
                msg = self.sub_socket.recv_json(flags=zmq.NOBLOCK)
                with self._hb_lock:
                    self._hb_latest_state = msg
                    self._hb_last_time = time.monotonic()
                    consecutive += 1
                    if consecutive >= 3:  # require 3 consecutive heartbeats to be considered online
                        self._hb_online = True
            except zmq.Again:
                with self._hb_lock:
                    if self._hb_last_time > 0:
                        if self._hb_online and (time.monotonic() - self._hb_last_time > self._hb_timeout):
                            self._hb_latest_state = {}
                            self._hb_last_time = 0
                            self._hb_online = False
                            consecutive = 0
                            logger_mp.warning("[IPC_Client] HeartBeat timeout -> OFFLINE")
            except Exception as e:
                logger_mp.error(f"[IPC_Client] HB loop exception: {e}")
            elapsed = time.monotonic() - start_time
            if elapsed < self._hb_interval:
                time.sleep(self._hb_interval - elapsed)

    # ---------------------------
    # Public API
    # ---------------------------
    def send_data(self, cmd: str) -> dict:
        """Send command to server and wait reply"""
        reqid = self._make_reqid()
        if not self.is_online():
            logger_mp.warning(f"[IPC_Client] Cannot send {cmd}, server offline (no heartbeat)")
            return {"repid": reqid, "status": "error", "msg": "server offline (no heartbeat)"}
        
        msg = {"reqid": reqid, "cmd": cmd}
        try:
            self.req_socket.send_json(msg)
            # wait up to 1s for reply
            if self.req_socket.poll(1000):
                reply = self.req_socket.recv_json()
            else:
                return {"repid": reqid, "status": "error", "msg": "timeout waiting for server reply"}
        except Exception as e:
            logger_mp.error(f"[IPC_Client] send_data failed: {e}")
            return {"repid": reqid, "status": "error", "msg": str(e)}

        if reply.get("status") != "ok":
            return reply
        if reply.get("repid") != reqid:
            return {"repid": reqid, "status": "error", "msg": f"reply id mismatch: expected {reqid}, got {reply.get('repid')}"}
        return reply

    def is_online(self) -> bool:
        with self._hb_lock:
            return self._hb_online

    def latest_state(self) -> dict:
        with self._hb_lock:
            return dict(self._hb_latest_state)
    
    def stop(self):
        self._hb_running = False
        if self._hb_thread:
            self._hb_thread.join(timeout=1.0)
        try:
            self.req_socket.setsockopt(zmq.LINGER, 0)
            self.req_socket.close()
        except Exception:
            pass
        try:
            self.sub_socket.setsockopt(zmq.LINGER, 0)
            self.sub_socket.close()
        except Exception:
            pass
        try:
            self.ctx.term()
        except Exception:
            pass


# ---------------------------
# Client Example usage
# ---------------------------
if __name__ == "__main__":
    from sshkeyboard import listen_keyboard, stop_listening
    client = None

    def on_press(key: str):
        global client
        if client is None:
            logger_mp.warning("⚠️ Client not initialized, ignoring key press")
            return

        if key == "r":
            logger_mp.info("▶️ Sending tracking toggle command...")
            rep = client.send_data("CMD_START")
            logger_mp.info("Reply: %s", rep)

        elif key == "s":
            logger_mp.info("⏺️ Sending record toggle command...")
            rep = client.send_data("CMD_RECORD_TOGGLE")
            logger_mp.info("Reply: %s", rep)
            

        elif key == "q":
            logger_mp.info("⏹️ Sending exit command...")
            rep = client.send_data("CMD_STOP")
            logger_mp.info("Reply: %s", rep)

        elif key == "b":
            if client.is_online():
                state = client.latest_state()
                logger_mp.info(f"[HEARTBEAT] Current heartbeat: {state}")
            else:
                logger_mp.warning("[HEARTBEAT] No heartbeat received (OFFLINE)")

        else:
            logger_mp.warning(f"⚠️ Undefined key: {key}")

    # Initialize client
    client = IPC_Client(hb_fps=10.0)

    # Start keyboard listening thread
    listen_keyboard_thread = threading.Thread(target=listen_keyboard, kwargs={"on_press": on_press, "until": None, "sequential": False}, daemon=True)
    listen_keyboard_thread.start()

    logger_mp.info("✅ Client started, waiting for keyboard input:\n [r] start/pause/resume tracking, [s] start/stop record, [b] heartbeat, [q] exit")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger_mp.info("⏹️ User interrupt, preparing to exit...")
    finally:
        stop_listening()
        client.stop()
        logger_mp.info("✅ Client exited")
