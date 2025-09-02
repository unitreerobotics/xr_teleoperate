import sys; sys.path.insert(0, '.')

import numpy as np
import sys, os, re, math, shutil, time, datetime
import cv2
import scipy.io as sio
from scipy.interpolate import UnivariateSpline, PchipInterpolator

from ..common import myglobals

def findNearestFrame(srcTimes, targetTimes):

    orderSrc = np.argsort(srcTimes)
    orderTarget = np.argsort(targetTimes)

    srcSorted = srcTimes[orderSrc]
    targetSorted = targetTimes[orderTarget]

    # find nearest frame for each resampled frame
    nearestFrame = np.zeros([len(srcTimes)], int)
            
    mi = 0
    for i in range(len(srcSorted)):
        while True:
            if mi == len(targetSorted) - 1:
                break
            if targetSorted[mi + 1] - srcSorted[i] > srcSorted[i] - targetSorted[mi]:
                break
            mi += 1
        nearestFrame[i] = mi

    # now we have nearest sorted target for each sorted source => invert the sorting

    # => get nearest target for each sorted source
    nearestFrame = orderTarget[nearestFrame]
    # => get nearest target for each source
    nearestFrame = nearestFrame[np.argsort(orderSrc)]

    return nearestFrame


def loadMetadata(filename, silent = False):
    try:
        # http://stackoverflow.com/questions/6273634/access-array-contents-from-a-mat-file-loaded-using-scipy-io-loadmat-python
        if not silent:
            print('\tReading metadata from %s...' % filename)
        #metadata = sio.loadmat(filename, squeeze_me=True, struct_as_record=False)
        metadata = MatReader().loadmat(filename)
    except:
        print('\tFailed to read the meta file "%s"!' % filename)
        return None
    return metadata

def resampleMeta(referenceTime, meta, channelFilter = [], nearestOnly = False):

    srcData = meta['data']
    srcTime = meta['header'].ts_secs

    # only use valid samples (definition may vary)
    srcValid = np.ones(srcTime.shape, np.bool)
            
    # check if there is confidence
    if 'confidence' in srcData._fieldnames:
        srcValid &= np.greater(srcData.confidence, 0.9)

    srcValid = np.argwhere(srcValid)[:,0]
    srcTime = srcTime[srcValid]

    # Remove oversampling (breaks interpolation with dt=0)
    srcTime, srcUnique = np.unique(srcTime, return_index = True)
    srcValid = srcValid[srcUnique]

    dstDt = np.mean(np.diff(referenceTime))
    srcDt = np.mean(np.diff(srcTime))
    print('\tResampling from %.2f FPS to %.2f FPS.' % (1.0 / srcDt, 1.0 / dstDt))
    #nearestOnly = False
    #if dstDt > 2 * srcDt:
    #    print('\t\t=> target framerate is significantly lower than source => will use nearest sampling only.')
    #    nearestOnly = True
    
    # Get nearest row
    nearestRow = findNearestFrame(referenceTime, srcTime)

    res = dict()
    res['header'] = dict()
    res['header']['ts_secs'] = referenceTime
    res['header']['frame'] = meta['header'].frame[nearestRow]

    res['data'] = dict()
    dstData = res['data']
    dstData['ts_secs_key'] = srcTime[nearestRow]

    # Each data channel
    for channel in srcData._fieldnames:
        if len(channelFilter) > 0 and not channel in channelFilter:
            continue
        print('\t\tProcessing channel %s...' % channel)
        cData = getattr(srcData, channel)
        cData = cData[srcValid]

        # Singular channels do not interpolate well
        if not isinstance(cData, np.ndarray) or len(cData) <= 0:
            print('\t\t\tSingular channel => just copy.')
            merged[channel] = cData
            continue
                
        origShape = cData.shape
        cData = cData.reshape([cData.shape[0],-1])

        oShape = np.array(cData.shape)
        oShape[0] = len(referenceTime)
        oData = np.zeros(oShape, cData.dtype)

        nDims = cData.shape[1] if len(cData.shape) >= 2 else 1

        # interpolation - always good idea?
        for dim in range(nDims):
            x = cData[:, dim]

            if not nearestOnly and issubclass(cData.dtype.type, float):
                # interpolate floats
                #if metaName == 'world_to_front_stitched':
                    #import pdb;pdb.set_trace()
                print('\t\t...pchip interpolation...')                                    
                spl = PchipInterpolator(srcTime, x, extrapolate = False) # pchip
                #spl = UnivariateSpline(srcTime, x, k = 1, s = 0, ext = 0) # lin
                oData[:,dim] = spl(referenceTime)

                # fix extrapolation and other nan
                nanInds = np.squeeze(np.argwhere(np.isnan(oData[:,dim])))
                oData[nanInds,dim] = x[nearestRow[nanInds]]
            else:
                # just take nearest for other types
                print('\t\t...nearest sampling...')
                oData[:,dim] = x[nearestRow] 
                                             
        if len(origShape) == 1:
            #cData = cData.reshape([cData.shape[0]])
            oData = oData.reshape([oData.shape[0]])
        else:
            oShape = np.array(origShape)
            oShape[0] = frameCount
            oData = oData.reshape(oShape)
                                    
        dstData['%s' % (channel)] = oData

    return res


def getIntervals(condition):
    intervals = []
    a = -1;
    for i in range(len(condition)):
        if condition[i]:
            if a < 0:
                a = i
        else:
            if a >= 0:
                intervals.append([a, i])
                a = -1
    if a >= 0:
        intervals.append([a, i])

    return np.array(intervals)

def dir2Angles(gaze3d):
    yaw = np.arctan2(gaze3d[:,0], -gaze3d[:,2])
    xz = gaze3d[:,[0,2]]
    xz = np.linalg.norm(xz, ord = 2, axis = 1)
    pitch = np.arctan2(gaze3d[:,1],xz)
    gazeAngles = np.stack([yaw, pitch],axis=1)
    return gazeAngles


def angles2Dir(angles):
    gaze3d = np.zeros([angles.shape[0], 3], angles.dtype)
    gaze3d[:,0] = np.sin(angles[:,0]) * np.cos(angles[:,1])
    gaze3d[:,2] = -np.cos(angles[:,0]) * np.cos(angles[:,1])
    gaze3d[:,1] = np.sin(angles[:,1])
    return gaze3d


def preparePath(path, clear = False):
    if not os.path.isdir(path):
        os.makedirs(path, 0o777)
    if clear:
        files = os.listdir(path)
        for f in files:
            fPath = os.path.join(path, f)
            if os.path.isdir(fPath):
                shutil.rmtree(fPath)
            else:
                os.remove(fPath)

    return path

def getUnixTimestamp():
    return np.datetime64(datetime.datetime.now()).astype(np.int64)   # unix TS in secs and microsecs


class MatReader(object):

    def __init__(self, flatten1D = True):
        self.flatten1D = flatten1D

    def loadmat(self, filename):
        meta = sio.loadmat(filename, struct_as_record=False) 
        
        meta.pop('__header__', None)
        meta.pop('__version__', None)
        meta.pop('__globals__', None)

        meta = self._squeezeItem(meta)
        return meta

    def _squeezeItem(self, item):
        if isinstance(item, np.ndarray):            
            if item.dtype == np.object:
                if item.size == 1:
                    item = item[0,0]
                else:
                    item = item.squeeze()
            elif item.dtype.type is np.str_:
                item = str(item.squeeze())
            elif self.flatten1D and len(item.shape) == 2 and (item.shape[0] == 1 or item.shape[1] == 1):
                #import pdb; pdb.set_trace()
                item = item.flatten()
            
            if isinstance(item, np.ndarray) and item.dtype == np.object:
                #import pdb; pdb.set_trace()
                #for v in np.nditer(item, flags=['refs_ok'], op_flags=['readwrite']):
                #    v[...] = self._squeezeItem(v)
                it = np.nditer(item, flags=['multi_index','refs_ok'], op_flags=['readwrite'])
                while not it.finished:
                    item[it.multi_index] = self._squeezeItem(item[it.multi_index])
                    it.iternext()



        if isinstance(item, dict):
            for k,v in item.items():
                item[k] = self._squeezeItem(v)
        elif isinstance(item, sio.matlab.mio5_params.mat_struct):
            for k in item._fieldnames:
                v = getattr(item, k)
                setattr(item, k, self._squeezeItem(v))
                 
        return item

  
class Bunch(object):
  def __init__(self, adict):
    self.__dict__.update(adict)