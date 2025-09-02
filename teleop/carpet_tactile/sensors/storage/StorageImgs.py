import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import multiprocessing as mp
import cv2

from storage.Storage import Storage
from app.AppContext import AppContext
from common import dataset_tools



class StorageImgs(Storage):
    
    # Implementation details
    def getName(self):
        return '%s (StorageImgs)' % self.name
    
    def _init(self):
        # Setup output
        tsFilename = os.path.join(dataset_tools.preparePath(self.outputPath), '%s.txt' % self.name)
        self.tsOut = open(tsFilename, 'w')

    def _release(self):
        self.tsOut.close()


    def _addFrame(self, ts, data):
        frameSubFolder = '%03dk' % (self.frameCount // 1000)
        framePath = dataset_tools.preparePath(os.path.join(self.opts.outputPath, self.name, frameSubFolder))
        filename = os.path.join(framePath, '%06d.jpg' % self.frameCount)
        if 'im_jpeg' in data:
            data['im_jpeg'].tofile(filename)
        elif 'im' in data:
            cv2.imwrite(filename, data['im'], [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            raise RuntimeError('No image data!')
        self.tsOut.write('%.10f\n' % ts)
        self.frameCount += 1


    