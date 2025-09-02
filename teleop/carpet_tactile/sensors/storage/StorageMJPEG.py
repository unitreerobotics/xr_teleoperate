import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import multiprocessing as mp
import cv2

from storage.Storage import Storage
from app.AppContext import AppContext
from common import dataset_tools



class StorageMJPEG(Storage):
    
    # Implementation details
    def getName(self):
        return '%s (StorageMJPEG)' % self.name
    
    def _init(self):
        # Setup output
        videoFilename = os.path.join(dataset_tools.preparePath(self.outputPath), '%s.avi' % self.name)
        self.log('Output file: %s' % videoFilename)
        self.videoOut = open(videoFilename, 'wb')

        tsFilename = os.path.join(self.outputPath, '%s.txt' % self.name)
        self.tsOut = open(tsFilename, 'w')

    def _release(self):
        self.videoOut.close()
        self.tsOut.close()


    def _addFrame(self, ts, data):
        assert 'im_jpeg' in data
        data['im_jpeg'].tofile(self.videoOut)

        self.tsOut.write('%.10f\n' % ts)

        self.frameCount += 1


    