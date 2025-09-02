import math
import numpy as np

def matrixInverseSafe(matrix):
    if np.fabs(np.linalg.det(matrix)) < 1e-3:
        return np.zeros(matrix.shape)
    try:
        return np.linalg.inv(matrix)
    except:
        return np.zeros(matrix.shape)

def lerp(a, b, c):
    return a + (b - a) * c

def bilinearInterp(y00, y10, y01, y11, xx, xy):
    return lerp(lerp(y00, y10, xx), lerp(y01, y11, xx), xy)

def clamp(x, a, b):
    return np.minimum(np.maximum(x, a), b)

def rotX(angleRad):
    s = math.sin(angleRad)
    c = math.cos(angleRad)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]], np.float32)

def rotY(angleRad):
    s = math.sin(angleRad)
    c = math.cos(angleRad)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]], np.float32)

def rotZ(angleRad):
    s = math.sin(angleRad)
    c = math.cos(angleRad)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]], np.float32)

def gauss(x, sigma = 1.0, mu = 0.0):
    return 1.0 / (sigma / np.sqrt(2.0 * np.pi)) * np.exp((-0.5 *((x - mu) * (x - mu))) / (sigma * sigma))
