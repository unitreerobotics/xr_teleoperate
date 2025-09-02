import sys; sys.path.insert(0, '.')

import numpy as np
import sys, os, re, time, shutil, math
from joblib import Parallel, delayed
from collections import OrderedDict
import cv2
import scipy.io as sio
try:
    import torch.multiprocessing as mp
except:
    import multiprocessing as mp
import ctypes


from ..common import myglobals, dataset_tools, image_tools

class LogEntry(object):

    COUNTER = 0

    def __init__(self, message, timeoutMs):
        super(LogEntry, self).__init__()
        self.guid = LogEntry.COUNTER
        LogEntry.COUNTER += 1

        self.created = dataset_tools.getUnixTimestamp()
        self.message = message
        self.timeoutMs = timeoutMs

    def isValid(self):
        if self.timeoutMs <= 0:
            return True
        ageMs = 1000*(dataset_tools.getUnixTimestamp() - self.created)
        return ageMs < self.timeoutMs


class AppLog(object):
    '''Manages log.'''
        
    def __init__(self):
        super(AppLog, self).__init__()
        #self.logQueue = DataQueueOrdered(limit = 0)
        #self.entries = []
        

    def log(self, message, timeoutMs = myglobals.DEFAULT_CONSOLE_TIMEOUT_MS):
        print(message)
        #entry = LogEntry(message, timeoutMs)
        #self.logQueue.push(entry)

    def consume(self):
        return
        while True:
            entry = self.logQueue.pop()
            if entry is None:
                break
            self.entries.append(entry)

    def clear(self):
        #self.entries.clear()
        pass

    def release(self):
        print('[AppLog] Releasing...')
        #self.logQueue.release()            
        print('[AppLog] Released.')

