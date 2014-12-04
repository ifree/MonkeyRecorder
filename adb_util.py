import os
import subprocess
import re


class Process:
    """
Simple subprocess wrapper
"""
    process = None
    stdout = None
    stderr = None

    def __init__(self, command):
        self.command = command
    
    def run(self):
        self.process = subprocess.Popen(self.command
                                        , stdout = subprocess.PIPE
                                        , stderr = subprocess.STDOUT)
        self.stdout = iter(self.process.stdout.readline, "")
#        self.stderr = iter(self.process.stderr.readline, "")
    
    def getLines(self):
        return self.stdout 

    def getExitCode(self):
        self.process.wait()
        return self.process.returncode

    def kill(self):
        "monkey runner use jython 2.5 and it doesen't offer this."
        killFn = getattr(self.process, "kill", None)
        if callable(killFn):
            self.process.kill()
        else:
            #jython 2.5 fallback
            self.process._process.destroy()

class AdbUtil:
    """Simple class to do some adb related task."""

    _target_arg = ""

    def asEmulator(self):
        "target is emulator"
        self._target_arg = "-e"

    def asDevice(self):
        "target is device"
        self._target_arg = "-d"

    def setSerial(self, serial):
        self._target_arg = "-s %s" % serial

    def sendCommand(self, command):
        "send adb command. TODO: poor performance? use singleton process obj."
        ret = Process("adb %s %s" % (self._target_arg, command))
        ret.run()
        return ret

    def listDevices(self):
        # from adb_host.py
        # Regex to find an adb device. Examples:
        # 0146B5580B01801B device
        # 018e0ecb20c97a62 device
        # 172.22.75.141:5555 device
        DEVICE_FINDER_REGEX = ('^(?P<SERIAL>([\w]+)|(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}))'
                               '([:]5555)?[ \t]+device')
        cmd = self.sendCommand("devices")
        devices = []
        for line in cmd.getLines():
            match = re.search(DEVICE_FINDER_REGEX, line)

            if match:
                devices.append(match.group("SERIAL"))
        cmd.kill()
        return devices
        
        
