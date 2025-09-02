import numpy as np
import sys, os, re, time, shutil, math
import scipy.io as sio
import multiprocessing as mp
import multiprocessing.managers as mpm
#import torch.multiprocessing as mp

from ..common import myglobals, dataset_tools

''' Loosely inspired by: https://pythonhosted.org/ruffus/html/sharing_data_across_jobs_example.html '''

class PerformanceMonitor(object):
        
    def __init__(self):
        super(PerformanceMonitor, self).__init__()
        self.reset()

    def tick(self, key, desc = ''):
        ts = dataset_tools.getUnixTimestamp()
        if not key in self.keyedTicks:
            self.keyedTicks[key] = []
        self.keyedTicks[key].append(ts)

        self.timestamps.append(ts)
        self.keys.append(key)
        self.descs.append(desc)
        #print('New keyedTicks is %d: %s' % (len(self.keyedTicks[key]), key))

    def report(self):
        res = dict()
        for k,v in self.keyedTicks.items():
            if len(v) < 2:
                res[k] = 0.0
                continue
            ts = v[-100:]
            dts = np.diff(ts)
            fps = 1.0 / np.mean(dts)
            res[k] = fps
        return res

    def dumpToFile(self, filename):
        print('[PerformanceMonitor] Dumping to %s...' % filename)
        meta = dict()
        meta['timestamp'] = np.array(self.timestamps, np.float)
        meta['key'] = np.array(self.keys, np.object)
        meta['desc'] = np.array(self.descs, np.object)
        sio.savemat(filename, meta)
        print('[PerformanceMonitor] Dumped to %s...' % filename)

    def reset(self):
        self.keyedTicks = dict()        
        self.timestamps = []
        self.keys = []
        self.descs = []


def setup_PerformanceMonitor():
    return PerformanceMonitor()

class PerformanceMonitorProxy(mpm.BaseProxy):
    def reset(self):
        return self._callmethod('reset', [])
    def tick(self, key, desc = ''):
        return self._callmethod('tick', [key, desc])
    def report(self):
        return self._callmethod('report', [])
    def dumpToFile(self, filename):
        return self._callmethod('dumpToFile', [filename])
    def __str__ (self):
        return "PerformanceMonitorProxy"
