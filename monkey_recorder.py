#!/usr/bin/env monkeyrunner
import os
import sys
import re
import math
import subprocess
import optparse
import operator
from com.android.monkeyrunner.recorder import MonkeyRecorder as recorder
from com.android.monkeyrunner import MonkeyRunner, MonkeyDevice
sys.path.append(os.path.dirname(__file__))
import adb_util
#from android monkey source

#TODO make export function easier

class Recorder:

    CMD_MAP = {
        'TOUCH': lambda dev, arg: Recorder.touch(dev,arg),
        'DRAG': lambda dev, arg: Recorder.drag(dev, arg),
        'PRESS': lambda dev, arg: dev.press(**arg),
        'TYPE': lambda dev, arg: dev.type(**arg),
        'WAIT': lambda dev, arg: MonkeyRunner.sleep(**arg)
    }

    #caching, and yes, global variable
    SCREEN = None
    ORIENT = None

    @staticmethod
    def get_orientation(dev):
        """if global variable `ORIENT` is None get current device's orientation"""
        #maybe windowmanager is better
        #Orient_Info = re.compile('\s*SurfaceOrientation:\s+(?P<orientation>\d)')
        if Recorder.ORIENT is None:
            #dev.shell("dumpsys")  ... very buggy due to jython's encoding handling
            (orient, _) = subprocess.Popen(""" sh -c "adb shell dumpsys | grep -m 1 -i surfaceorientation | awk '{ print $2 }'" """
                                        , stdout = subprocess.PIPE
                                        , stderr = subprocess.STDOUT)\
                      .communicate()
            
            Recorder.ORIENT = int(orient)
            
        return Recorder.ORIENT

    @staticmethod
    def get_screen(dev):
        """if global valiable `SCREEN` is None the get current devices' SCREEN coord"""
        if Recorder.SCREEN is None:
            Recorder.SCREEN = (float(dev.getProperty('display.width'))
                  , float(dev.getProperty('display.height')))

        return Recorder.SCREEN
    
    @staticmethod
    def trans_coord(tup, reverse = False, OtherScreen = None, OtherOrient = None):
        """transform coordinate according to `OtherScreen`, `OtherOrient` if it is not None, otherwise use global variable `SCREEN`, `ORIENT`"""
        
        x, y = float(tup[0]), float(tup[1]) #avoid losing precision
        op = (lambda _x, _y: int(_x * _y)) if reverse else operator.div
        screen = OtherScreen if OtherScreen is not None else Recorder.SCREEN
        orient = OtherOrient if OtherScreen is not None else Recorder.ORIENT

        rotationMat = [
            (1, 0,
             0, 1),#0 no rotate
            (0, 1,
             -1, 0),#1 rotate 270 , counterclockwise
            (-1, 0,
             0, -1),#2 rotate 180
            (0, 1,
             -1, 0)#3 rotate 270, clockwise
        ]
        
        mul = lambda x, y, mat : (x * mat[0] + y * mat[1]
                                  , x * mat[2] + y * mat[3])

        x, y = mul(x, y, rotationMat[orient]) # matrix rotation

        if reverse:#to screen coordinate
            x, y = x if x > 0 else 1 + x,  y if y > 0 else 1 + y #fix coordinate
            x, y = op(x, screen[0]), op(y, screen[1])  
        if not reverse:#to percent
            x, y = op(x, screen[0]), op(y, screen[1]) 
            x, y = x if x > 0 else 1 + x,  y if y > 0 else 1 + y 
            
        
        return (x, y) if not reverse else (int(x), int(y))
    
    @staticmethod
    def touch(dev, arg):
        coord = Recorder.trans_coord((arg['x'], arg['y']) , True)
        arg['x'], arg['y'] = coord[0], coord[1]
        dev.touch(**arg)

    @staticmethod
    def drag(dev, arg):
        arg['end'] = Recorder.trans_coord(arg['end'],True)
        arg['start'] = Recorder.trans_coord(arg['start'],True)
        dev.drag(**arg)
    
    
    def __init__(self, device):
        self.device = device;    

    def record(self):
        #jython can't access private fileds, so just start original recorder
        recorder.start(self.device)

    def fixPos(self, config):
        """convert absolute pos to percentage
        try to read config from `config`, if `config` contains
        config info, eg: CONFIG|{'orient':0, 'screen':(1200, 800)}
        
"""
        #monkey_recorder always use potrait
        (cmd, rest) = config.readline().split('|')
        rest = eval(rest)
        if cmd == "CONFIG":
            orientation = rest['orient']
            screen = rest['screen']
        else:
            sys.exit("invalid config!")

        for line in config:
            if line[0] == "#":
                continue
            (cmd, rest) = line.split('|')
            try:
                rest = eval(rest)
            except:
                print 'unable to parse options'
                continue
            if cmd not in Recorder.CMD_MAP:
                print 'unknow command:' + cmd
                continue
            if cmd == 'DRAG':
                rest['start'] = Recorder.trans_coord(rest['start'], False, screen, orientation)
                rest['end'] = Recorder.trans_coord(rest['end'], False, screen, orientation)
                
            elif cmd == 'TOUCH':
                rest['x'] ,rest['y'] = Recorder.trans_coord((rest['x'] ,rest['y']), False, screen, orientation)
            yield (cmd, rest)


        
    def play(self, config):
        #init global variables
        #Recorder.SCREEN = (1200, 1920)
        #Recorder.ORIENT = 1
        Recorder.get_screen(self.device)
        Recorder.get_orientation(self.device)
        fixedPos = self.fixPos(config)
        for pos in fixedPos:
            cmd, rest = pos

            if cmd not in Recorder.CMD_MAP:
                print 'unknow command:' + cmd
                continue
            print "exec command %s " % cmd
            Recorder.CMD_MAP[cmd](self.device, rest)


if __name__ == "__main__":
    parser = optparse.OptionParser(
        description = "Android action recorder"
        , prog = "monkeyrunner")
    
    parser.add_option('-s', '--device'
                          , help = "device id")
        
    parser.add_option('-a', '--action'
                          , help = "action type, record or play"
        )

    parser.add_option('-f', '--file', dest = "target_file", help = "file name to record or play, default is stdin or stdout")

    #only work for play
    parser.add_option('-o', '--orientation'
                      , type = "int"
                      , help = "orientation settings"
                      ", 0 for portait"
                      ", 1 for 90 counterclockwise"
                      ", 3 for 90 clockwise")

    (args, _) = parser.parse_args()
    
    from adb_util import AdbUtil

    adb = AdbUtil()
    device = args.device if args.device is  not None else adb.listDevices()[0]
    rec = Recorder(MonkeyRunner.waitForConnection(20 ,device))
    record_config = None

    if args.action == 'record':
        rec.record()
        
    elif args.action == 'play':
        if args.orientation is not None:
            Recorder.ORIENT = args.orientation
        record_config = sys.stdin if args.target_file is None else open(args.target_file, 'r')
        rec.play(record_config)
        
    elif args.action == 'fix':
        record_config = sys.stdin if args.target_file is None else open(args.target_file, 'r')
        poses = rec.fixPos(record_config)
        for pos in poses:
            print "%s|%s" % pos
    else:
        print "orient is: %s, screen is %s" % (Recorder.get_orientation(rec.device)
                                               , Recorder.get_screen(rec.device))
        

