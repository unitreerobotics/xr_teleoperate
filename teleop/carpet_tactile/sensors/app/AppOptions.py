import numpy as np
import sys, os, re, time, shutil, math, argparse, datetime

class AppOptions(object):

    def __init__(self, parser):
        self.parser = parser

    def getCmd(self, mods = None):
        args = self.parser.parse_args()
        if not mods is None:
            args = self.applyMods(args, mods)
        return args

    def getDefault(self, mods = None):
        args = self.parser.parse_args()
        for key in vars(args):
            setattr(args, key, self.parser.get_default(key))
        if not mods is None:
            args = self.applyMods(args, mods)
        return args

    def applyMods(self, args, mods):
        for k,v in mods.items():
            setattr(args, k, v)
        return args
