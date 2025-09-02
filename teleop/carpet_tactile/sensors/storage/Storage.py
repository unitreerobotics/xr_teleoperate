import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import multiprocessing as mp
import cv2

from ..app.AppContext import AppContext

class Storage(object):

    def __init__(self, outputPath, name, ctx, opts):
        self.outputPath = outputPath
        self.name = name
        self.ctx = ctx
        self.opts = opts
        self.init()
        super(Storage, self).__init__()

    def reset(self):
        self.release()

    def init(self):
        self.frameCount = 0
        self._init()

    def release(self):
        self._release()
        self.log('Released.')

    def addFrame(self, ts, data):
        self._addFrame(ts, data)

    def log(self, msg):
        self.ctx.log('[%s] %s' % (self.getName(), msg))

    def __len__(self):
        return self.frameCount


    # Implementation details
    def getName(self):
        return None
    
    def _init(self):
        pass

    def _release(self):
        pass


    def _addFrame(self, ts, data):
        pass


def createStorage(storageType, outputPath, name, ctx, opts):

    if storageType == 'dummy':
        from storage.StorageDummy import StorageDummy
        StorageClass = StorageDummy
    elif storageType == 'video':
        from storage.StorageVideo import StorageVideo
        StorageClass = StorageVideo
    elif storageType == 'mjpeg':
        from storage.StorageMJPEG import StorageMJPEG
        StorageClass = StorageMJPEG
    elif storageType == 'imgs':
        from storage.StorageImgs import StorageImgs
        StorageClass = StorageImgs
    elif storageType == 'audio':
        from storage.StorageAudio import StorageAudio
        StorageClass = StorageAudio
    elif storageType == 'hdf5':
        from ..storage.StorageHDF5 import StorageHDF5
        StorageClass = StorageHDF5
    else:
        RuntimeError('Unknown storage "%s"' % storageType)
    return StorageClass(outputPath, name, ctx, opts)
