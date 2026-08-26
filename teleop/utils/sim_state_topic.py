# Copyright (c) 2025, Unitree Robotics Co., Ltd. All Rights Reserved.
# License: Apache License, Version 2.0  
"""
Simple sim state subscriber class
Subscribe to rt/sim_state_cmd topic and write to shared memory
"""

import threading
import time
import json
from multiprocessing import shared_memory
from typing import Any, Dict, Optional
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_

import logging_mp
logger_mp = logging_mp.getLogger(__name__)


class SharedMemoryManager:
    """Shared memory manager"""
    
    def __init__(self, name: Optional[str] = None, size: int = 512):
        """Initialize shared memory manager
        
        Args:
            name: shared memory name, if None, create new one
            size: shared memory size (bytes)
        """
        self.size = size
        self.lock = threading.RLock()  # reentrant lock
        
        if name:
            try:
                self.shm = shared_memory.SharedMemory(name=name)
                self.shm_name = name
                self.created = False
            except FileNotFoundError:
                self.shm = shared_memory.SharedMemory(create=True, size=size)
                self.shm_name = self.shm.name
                self.created = True
        else:
            self.shm = shared_memory.SharedMemory(create=True, size=size)
            self.shm_name = self.shm.name
            self.created = True
    
    def write_data(self, data: Dict[str, Any]) -> bool:
        """Write data to shared memory
        
        Args:
            data: data to write
            
        Returns:
            bool: write success or not
        """
        try:
            with self.lock:
                json_str = json.dumps(data)
                json_bytes = json_str.encode('utf-8')
                
                if len(json_bytes) > self.size - 8:  # reserve 8 bytes for length and timestamp
                    logger_mp.warning(f"Data too large for shared memory ({len(json_bytes)} > {self.size - 8})")
                    return False
                
                # write timestamp (4 bytes) and data length (4 bytes)
                timestamp = int(time.time()) & 0xFFFFFFFF  # 32-bit timestamp, use bitmask to ensure in range
                self.shm.buf[0:4] = timestamp.to_bytes(4, 'little')
                self.shm.buf[4:8] = len(json_bytes).to_bytes(4, 'little')
                
                # write data
                self.shm.buf[8:8+len(json_bytes)] = json_bytes
                return True
                
        except Exception as e:
            logger_mp.error(f"Error writing to shared memory: {e}")
            return False
    
    def read_data(self) -> Optional[Dict[str, Any]]:
        """Read data from shared memory
        
        Returns:
            Dict[str, Any]: read data dictionary, return None if failed
        """
        try:
            with self.lock:
                # read timestamp and data length
                timestamp = int.from_bytes(self.shm.buf[0:4], 'little')
                data_len = int.from_bytes(self.shm.buf[4:8], 'little')
                
                if data_len == 0:
                    return None
                
                # read data
                json_bytes = bytes(self.shm.buf[8:8+data_len])
                data = json.loads(json_bytes.decode('utf-8'))
                data['_timestamp'] = timestamp  # add timestamp information
                return data
                
        except Exception as e:
            logger_mp.error(f"Error reading from shared memory: {e}")
            return None
    
    def get_name(self) -> str:
        """Get shared memory name"""
        return self.shm_name
    
    def cleanup(self):
        """Clean up shared memory"""
        if hasattr(self, 'shm') and self.shm:
            self.shm.close()
            if self.created:
                try:
                    self.shm.unlink()
                except:
                    pass
    
    def __del__(self):
        """Destructor"""
        self.cleanup()

class SimStateSubscriber:
    """Simple sim state subscriber class"""
    
    def __init__(self, shm_name: str = "sim_state_cmd_data", shm_size: int = 16384):
        """Initialize the subscriber
        
        Args:
            shm_name: shared memory name
            shm_size: shared memory size
        """
        self.shm_name = shm_name
        self.shm_size = shm_size
        self.running = False
        self.subscriber = None
        self.subscribe_thread = None
        self.shared_memory = None
        
        # initialize shared memory
        self._setup_shared_memory()
        
        logger_mp.debug(f"[SimStateSubscriber] Initialized with shared memory: {shm_name}")
    
    def _setup_shared_memory(self):
        """Setup shared memory"""
        try:
            self.shared_memory = SharedMemoryManager(self.shm_name, self.shm_size)
            logger_mp.debug(f"[SimStateSubscriber] Shared memory setup successfully")
        except Exception as e:
            logger_mp.error(f"[SimStateSubscriber] Failed to setup shared memory: {e}")
    
    def start_subscribe(self):
        """Start subscribing"""
        if self.running:
            logger_mp.warning(f"[SimStateSubscriber] Already running")
            return
        
        try:
            self.subscriber = ChannelSubscriber("rt/sim_state", String_)
            self.subscriber.Init()
            self.running = True

            self.subscribe_thread = threading.Thread(target=self._subscribe_sim_state, daemon=True)
            self.subscribe_thread.start()

            logger_mp.info(f"[SimStateSubscriber] Started subscribing to rt/sim_state")
            
        except Exception as e:
            logger_mp.error(f"[SimStateSubscriber] Failed to start subscribing: {e}")
            self.running = False

    def _subscribe_sim_state(self):
        """Subscribe loop thread"""
        logger_mp.debug(f"[SimStateSubscriber] Subscribe thread started")
        
        while self.running:
            try:
                if self.subscriber:
                    msg = self.subscriber.Read()
                    if msg:
                        data = json.loads(msg.data)
                    else:
                        logger_mp.warning("[SimStateSubscriber] Received None message")
                    if self.shared_memory and data:
                        self.shared_memory.write_data(data)
                else:
                    logger_mp.error("[SimStateSubscriber] Subscriber is not initialized")
                time.sleep(0.002)
            except Exception as e:
                logger_mp.error(f"[SimStateSubscriber] Error in subscribe loop: {e}")
                time.sleep(0.01)

    def stop_subscribe(self):
        """Stop subscribing"""
        if not self.running:
            logger_mp.warning(f"[SimStateSubscriber] Already stopped or not running")
            return

        self.running = False
        # wait for thread to finish
        if self.subscribe_thread:
            self.subscribe_thread.join(timeout=1.0)

        if self.shared_memory:
            self.shared_memory.cleanup()
        logger_mp.info(f"[SimStateSubscriber] Subscriber stopped")
    
    def read_data(self) -> Optional[Dict[str, Any]]:
        """Read data from shared memory
        
        Returns:
            Dict: received data, None if no data or error
        """
        try:
            if self.shared_memory:
                return self.shared_memory.read_data()
            return None
        except Exception as e:
            logger_mp.error(f"[SimStateSubscriber] Error reading data: {e}")
            return None
    
    def is_running(self) -> bool:
        """Check if subscriber is running"""
        return self.running


def start_sim_state_subscribe(shm_name: str = "sim_state_cmd_data", shm_size: int = 16384) -> SimStateSubscriber:
    """Start sim state subscribing
    
    Args:
        shm_name: shared memory name  
        shm_size: shared memory size
        
    Returns:
        SimStateSubscriber: started subscriber instance
    """
    subscriber = SimStateSubscriber(shm_name, shm_size)
    subscriber.start_subscribe()
    return subscriber


# if __name__ == "__main__":
#     # example usage
#     logger_mp.info("Starting sim state subscriber...")
#     ChannelFactoryInitialize(1) # 0 for real robot, 1 for simulation
#     # create and start subscriber
#     subscriber = start_sim_state_subscribe()
    
#     try:
#         # keep running and check for data
#         while True:
#             data = subscriber.read_data()
#             if data:
#                 logger_mp.info(f"Read data: {data}")
#             time.sleep(1)
            
#     except KeyboardInterrupt:
#         logger_mp.warning("\nInterrupted by user")
#     finally:
#         subscriber.stop_subscribe()
#         logger_mp.info("Subscriber stopped") 
