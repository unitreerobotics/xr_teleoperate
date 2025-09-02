import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import multiprocessing as mp
import cv2

from storage.Storage import Storage
from app.AppContext import AppContext
from common import dataset_tools



class StorageDummy(Storage):
    '''
    Does not store anything.
    '''
    
    # Implementation details
    def getName(self):
        return '%s (StorageDummy)' % self.name
    
    def _init(self):
        pass

    def _release(self):
        pass


    def _addFrame(self, ts, data):
        self.frameCount += 1


    