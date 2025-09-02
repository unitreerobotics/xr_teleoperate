import os, sys, inspect, imp, math
import platform, tempfile

def isWindows():
    #return False
    return platform.system() == 'Windows'

def isServer():
    #return False
    return not isWindows()

def supportsGUI():
    #return False
    return not isServer()

APP_ROOT_PATH = os.path.realpath(os.path.abspath(os.path.join(os.path.split(inspect.getfile( inspect.currentframe() ))[0],"..")))
TEMP_PATH = tempfile.gettempdir()

CAMERA_LATENCY_MS = 800#400 
DEFAULT_CONSOLE_TIMEOUT_MS = 5000
PERFORMANCE_LOG_ENABLED = False



