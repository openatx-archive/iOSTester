# coding: utf-8
# Author: codeskyblue

import os
import threading
import time
import subprocess
import wda
from six.moves import queue
from logzero import logger
import atexit
import signal
import subprocess

import wdadb

_DEVNULL = open(os.devnull, 'wb')


class IDevice(object):
    """ IOS Device """
    def __init__(self, udid: str, port: int, hookfunc, name=''):
        self._udid = udid
        self._port = port
        self._que = queue.Queue()
        self._hookfunc = hookfunc
        self._name = name

        self._iproxy_proc = subprocess.Popen(
            ["iproxy", str(port), "8100", udid], stdout=_DEVNULL, stderr=_DEVNULL)
        self._wdaproc = None
        self._ok = threading.Event()
        self._ok.set()
        self._output_fd = open("logs/%s-wdalog.txt" % udid, "wb")
        self._client = wda.Client("http://localhost:%d" % port)
        self._last_status = None
        self.init_thread()
    
    @property
    def udid(self):
        return self._udid

    def hook(self, status: str):
        """
        Hook when status change

        Args:
            status: <preparing | idle | offline>  occupied
        """
        if not self._hookfunc:
            return
        if self._last_status == status:
            return
        self._last_status = status
        self._hookfunc(self, status)

    def set_offline(self):
        self._ok.clear()

    def init_thread(self):
        logger.info("%s start watch thread", self._udid)
        self._wth = threading.Thread(
            target=self._watch, name=self._udid + ":watch")
        self._wth.daemon = True
        self._wth.start()

    def start_wda(self):
        if self._wdaproc:
            logger.warning("wda proc thread is already started")
            return
        self._wda_started = time.time()
        self._wdaproc = subprocess.Popen(
            ['sh', 'runwda.sh', self._udid], stdout=_DEVNULL, stderr=self._output_fd)

    def stop_wda(self):
        logger.info("%s stop wda", self._udid)
        if self._wdaproc is None:
            logger.warning("%s wda is already killed", self._udid)
            return
        self._wdaproc.terminate()
        self._wdaproc = None

    def is_wda_ok(self):
        try:
            self._client.status()
            return True
        except:
            return False

    def _watch(self):
        while True:
            if self._ok.is_set():
                if not self._wdaproc:
                    logger.info("%s start WDA", self._udid)
                    self.start_wda()
                # should check here
                if self.is_wda_ok():
                    self.hook("idle")
                    logger.info("%s WDA is ready to use", self._udid)
                else:
                    self.hook("preparing")
                    logger.info("%s WDA is still waiting", self._udid)
                    # time.sleep(10)

                    if time.time() - self._wda_started > 30:
                        logger.warning(
                            "%s WDA is down, restart after 3s", self._udid)
                        self.stop_wda()  # restart
            else:
                self.hook("offline")
                self.stop_wda()
                self._ok.wait()

            time.sleep(3)


def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


__port = 8100


def free_port():
    global __port
    for i in range(20):
        if not is_port_in_use(__port + i):
            __port += i
            return __port
    raise RuntimeError("No free port can be found, should not happens")


device_ports = {}


def get_device_port(udid: str):
    if udid in device_ports:
        return device_ports[udid]
    port = free_port()
    device_ports[udid] = port
    return port


def udid2name(udid):
    try:
        p = subprocess.run(['idevicename', '-u', udid], capture_output=True, check=True)
        return p.stdout.strip().decode('utf-8')
    except subprocess.CalledProcessError:
        return 'unknown'


def list_devices():
    """
    Returns:
        dict {udid: name}
    """
    p = subprocess.run(['idevice_id', '-l'], capture_output=True, check=True)
    udids = p.stdout.strip().decode('utf-8').splitlines()
    return {udid: udid2name(udid) for udid in udids}


def main():
    ios_devices = {}
    idevice_map = {}

    # stop all process
    os.setpgrp()

    def cleanup():
        os.killpg(0, signal.SIGKILL)

    atexit.register(cleanup)

    def hookfunc(idevice, status):
        """ id, name, port, status """
        wdadb.device_save(idevice._udid, {
            "port": idevice._port,
            "name": idevice._name,
            "status": status,
        })
        logger.info(">>> %s [%s]", udid, status)

    # init all
    os.makedirs("logs", exist_ok=True)
    wdadb.device_reset()

    while True:
        current_devs = list_devices()
        offline_devs = set(ios_devices.keys()).difference(current_devs.keys())
        online_devs = set(current_devs.keys()).difference(ios_devices.keys())

        ios_devices = current_devs

        for udid in online_devs:
            # stop wda watch
            port = get_device_port(udid)
            logger.info("UDID: %s came online, port: %d", udid, port)
            if udid not in idevice_map:
                idevice_map[udid] = IDevice(udid, port, hookfunc, name=ios_devices[udid])
            idevice_map[udid]._ok.set()

        for udid in offline_devs:
            logger.warning("UDID: %s went offline" % udid)
            # start iproxy and wda watch(start wda, pull status() and check if cmd finished)
            idevice_map[udid].set_offline()
        time.sleep(.5)


if __name__ == "__main__":
    main()
