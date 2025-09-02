import numpy as np
import sys, os, re, time, shutil, math, argparse, datetime
import scipy.io as sio
import multiprocessing as mp
import multiprocessing.managers as mpm

from ..common import myglobals, dataset_tools, input_tools
from ..app.AppLog import *
from ..app.PerformanceMonitor import *

class AppContext(object):
    '''Manages log.'''
        
    def __init__(self, manager):
        super(AppContext, self).__init__()

        self.appLog = AppLog()
        #self.performanceMonitor = manager.setupPerformanceMonitor()
        self.runDate = datetime.datetime.now()


    def release(self):
        if myglobals.PERFORMANCE_LOG_ENABLED:
            self.performanceMonitor.dumpToFile(os.path.join(myglobals.DATA_PATH, 'live', 'performance.mat'))
        self.appLog.release()


    # Proxies
    def log(self, message, timeoutMs = myglobals.DEFAULT_CONSOLE_TIMEOUT_MS):
        return self.appLog.log(message, timeoutMs)

    def print(self, message, timeoutMs = myglobals.DEFAULT_CONSOLE_TIMEOUT_MS):
        return self.appLog.log(message, timeoutMs)

    def tick(self, key, desc = ''):
        return None
        return self.performanceMonitor.tick(key, desc)

    @staticmethod
    def create():
        manager = LgManager()
        #manager.start()
        ctx = AppContext(manager)
        return ctx



class LgManager(mpm.SyncManager): pass
    #'''Manages resources.'''
        
#LgManager.register('setupPerformanceMonitor', setup_PerformanceMonitor, proxytype=PerformanceMonitorProxy, exposed = ('reset', 'tick', 'report', 'dumpToFile', '__str__'))
