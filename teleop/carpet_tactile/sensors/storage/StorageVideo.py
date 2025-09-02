import sys; sys.path.insert(0, '.')
import sys, os, re, time, shutil, math, random, datetime, argparse, signal
import numpy as np
import multiprocessing as mp
import cv2

from storage.Storage import Storage
from app.AppContext import AppContext
from common import dataset_tools



class StorageVideo(Storage):
    
    # Implementation details
    def getName(self):
        return '%s (StorageVideo)' % self.name
    
    def _init(self):
        # Setup output
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        #fourcc = cv2.VideoWriter_fourcc(*'XVID')
        videoFilename = os.path.join(dataset_tools.preparePath(self.outputPath), '%s.avi' % self.name)
        self.log('Output file: %s' % videoFilename)
        self.videoOut = cv2.VideoWriter(videoFilename, fourcc, self.opts.fps, (int(self.opts.w), int(self.opts.h)))

        tsFilename = os.path.join(self.outputPath, '%s.txt' % self.name)
        self.tsOut = open(tsFilename, 'w')

    def _release(self):
        self.videoOut.release()
        self.videoOut = None
        self.tsOut.close()


    def _addFrame(self, ts, data):
        if 'im' in data:
            im = data['im']
        elif 'im_jpeg' in data:
            im = cv2.imdecode(data['im_jpeg'], cv2.IMREAD_COLOR)
        else:
            raise RuntimeError('No image data!')

        self.videoOut.write(im)
        self.tsOut.write('%.10f\n' % ts)

        self.frameCount += 1


    