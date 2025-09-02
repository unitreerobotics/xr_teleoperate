import sys
from ..common import myglobals

def readKeyAsync():
    if myglobals.isWindows():
        import msvcrt
        return ord(msvcrt.getch()) if msvcrt.kbhit() else 0
    else:
        import select
        res = 0
        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline()
            if line and res == 0:
                res = ord(line[0])
        return res

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')