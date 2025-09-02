import sys, os, re, time, shutil, math, random, datetime, argparse, signal, traceback
import multiprocessing as mp
import numpy as np

class FramerateMonitor(object):
    def __init__(self, maxAgeSec = 2.0, maxSamples = 120):
        self.maxAgeSec = maxAgeSec
        self.maxSamples = maxSamples
        self.reset()
        super(FramerateMonitor, self).__init__()

    def tick(self):
        self.ts += [time.time()]
        self._update()

    def reset(self):
        self.ts = []

    def _update(self):
        self.ts = self.ts[-self.maxSamples:]
        now = time.time()
        for i in range(len(self.ts) - 1, -1, -1):
            if now - self.ts[i] > self.maxAgeSec:
                self.ts = self.ts[i+1:]
                break


    def getFps(self):
        if len(self.ts) < 2:
            return -1
        return (len(self.ts) - 1) / max(self.ts[-1] - self.ts[0], 1e-3)

