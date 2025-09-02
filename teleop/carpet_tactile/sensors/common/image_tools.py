import numpy as np
import cv2
import math, os, re
from subprocess import DEVNULL, STDOUT, check_call, CalledProcessError
from ..common import myglobals

def fitImageToBounds(img, bounds, upscale = False, interpolation = cv2.INTER_LINEAR):
    inAsp = img.shape[1] / img.shape[0]
    outAsp = bounds[0] / bounds[1]

    if not upscale and img.shape[1] <= bounds[0] and img.shape[0] <= bounds[1]:
        return img
    elif img.shape[1] == bounds[0] and img.shape[0] == bounds[1]:
        return img

    if inAsp < outAsp:
        # Narrow to wide
        height = bounds[1]
        width = math.floor(inAsp * height+ 0.5)
    else:
        width = bounds[0]
        height = math.floor(width / inAsp + 0.5)

    res = cv2.resize(img, (int(width), int(height)), interpolation = interpolation)
    if len(res.shape) < len(img.shape):
        res = res[..., np.newaxis]
    return res

def letterBoxImage(img, size, return_bbox = False):
    # letter box
    szIn = np.array([img.shape[1], img.shape[0]])
    x0 = (size - szIn) // 2
    x1 = x0 + szIn

    res = np.zeros([size[1], size[0], img.shape[2]], img.dtype)
    res[x0[1]:x1[1],x0[0]:x1[0],:] = img

    if return_bbox:
        return res, np.concatenate((x0,x1-x0))

    return res

def resizeImageLetterBox(img, size, interpolation = cv2.INTER_LINEAR, return_bbox = False):
    img = fitImageToBounds(img, size, upscale = True, interpolation = interpolation)
    return letterBoxImage(img, size, return_bbox)
    

def cropImage(img, bboxRel, padding = True):
    bbox = (np.array(bboxRel, float) * [img.shape[1], img.shape[0], img.shape[1], img.shape[0]]).astype(int)

    aSrc = np.maximum(bbox[:2], 0)
    bSrc = np.minimum(bbox[:2] + bbox[2:], (img.shape[1], img.shape[0]))

    aDst = aSrc - bbox[:2]
    bDst = aDst + (bSrc - aSrc)
    if np.any(np.less_equal(bDst, aDst)):
        return None
    if np.any(np.less_equal(bSrc, aSrc)):
        return None

    src = img[aSrc[1]:bSrc[1],aSrc[0]:bSrc[0],:]
    if padding:
        res = np.zeros((bbox[3], bbox[2], img.shape[2]), img.dtype)    
        res[aDst[1]:bDst[1],aDst[0]:bDst[0],:] = src
    else:
        res = src

    return res


def fillImage(img, color):
    cv2.rectangle(img, (0, 0), (img.shape[1], img.shape[0]), tuple(map(int,color)), -1)


def pasteImage(dest, img, posRel, sizeRel = None, interpolation = cv2.INTER_LINEAR):
    aDst = (np.array(posRel, float) * [dest.shape[1], dest.shape[0]]).astype(int)
    if sizeRel is None:
        bDst = aDst + [img.shape[1], img.shape[0]]
    else:
        sz = (np.array(sizeRel, float) * [dest.shape[1], dest.shape[0]]).astype(int)
        bDst = aDst + sz
        img = cv2.resize(img, (int(sz[0]), int(sz[1])), interpolation = interpolation)

    aDstSafe = np.minimum(np.maximum(aDst, 0), [dest.shape[1] - 1, dest.shape[0] - 1])
    bDstSafe = np.minimum(np.maximum(bDst, aDstSafe), [dest.shape[1] - 1, dest.shape[0] - 1])
    if np.any(bDstSafe <= aDstSafe):
        return dest

    aSrc = aDstSafe - aDst
    bSrc = aSrc + (bDstSafe - aDstSafe)
    dest[aDstSafe[1]:bDstSafe[1],aDstSafe[0]:bDstSafe[0],:] = img[aSrc[1]:bSrc[1],aSrc[0]:bSrc[0],:]
    return dest

    
    


def gridImages(imgs, targetAspect = 16.0 / 10, layout = None):
    N = len(imgs)
    if layout is None:
        aspect = imgs[0].shape[1] / imgs[0].shape[0]
        gridAspect = targetAspect / aspect
        h = math.ceil(math.exp((math.log(N) - math.log(gridAspect)) / 2))
        w = math.ceil(N / h)
    else:
        w = layout[0]
        h = layout[1]

    rows = []    
    i = 0
    for y in range(h):
        row = []
        for x in range(w):
            if i < N:
                row += [imgs[i]]
                i += 1
            else:
                row += [np.zeros_like(imgs[0])]
        rows += [np.concatenate(row, axis=1)]
    res = np.concatenate(rows, axis=0)
    return res


def makeVideo(framesDir, pattern = '*.jpg', framerate = 8, outputVideoFile = None, overwrite = True):
    print('Making video for %s...' % (framesDir))

    videoName = os.path.basename(framesDir)
    
    if outputVideoFile is None:
        outputVideoFile = '%s/../%s.mp4' % (framesDir, videoName)
    outputVideoFile = os.path.realpath(outputVideoFile)
    if not overwrite and os.path.isfile(outputVideoFile):
        print('\tAlready exists => skipping...\n')
        return 
    
    cmdArgs = ['ffmpeg', '-r', '%f' % framerate]
    if myglobals.isWindows():
        # Windows does not support glob
        extension = os.path.splitext(pattern)[-1]
        cmdArgs += ['-i', '"%s\\%%06d%s"' % (framesDir, extension)]
    else:
        cmdArgs += ['-pattern_type', 'glob',
                '-i', "%s/%s" % (framesDir, pattern)]

    cmdArgs += ['-r', '30', 
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                '-crf', '21', '-pix_fmt', 'yuv420p', '-y', '"%s"' % outputVideoFile]
    cmdFull = ' '.join(cmdArgs)
    print('\t>> %s' % cmdFull)
    
    #if myglobals.isWindows():
    #    return False

    try:            
        outputStream = DEVNULL
        tempLogFile = os.path.join(myglobals.TEMP_PATH, 'my-ffmpeg.log')
        with open(tempLogFile, 'w') as fid:
            outputStream = fid
            if myglobals.isWindows():
                check_call(cmdFull, stdout=outputStream, stderr=outputStream)
            else:
                check_call(cmdArgs, stdout=outputStream, stderr=outputStream)
    except CalledProcessError as error:
        print('\tFFMPEG failed: System error! %s' % error)
        if os.path.isfile(tempLogFile):
            with open(tempLogFile, 'r') as fid:
                print(''.join(fid.readlines()))
        if os.path.isfile(outputVideoFile):
            os.unlink(outputVideoFile)
        return False
    
    if not os.path.isfile(outputVideoFile):
        print('\tFFMPEG failed: No results!')
        return False

    print('\tdone.')
    return True