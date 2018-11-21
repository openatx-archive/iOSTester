#!/usr/bin/env python3
# coding: utf-8
#
# author: codeskyblue

import os
import threading
import time
import subprocess
import wda
import queue
import atexit
import signal
import subprocess

# import wdadb

import logzero
from logzero import logger
import logging
import rethinkdb as r
from rethinkdb.errors import RqlRuntimeError, RqlDriverError

_DEVNULL = open(os.devnull, 'wb')
logzero.loglevel(logging.INFO)


RDB_HOST = os.environ.get('RDB_HOST') or 'localhost'
RDB_PORT = os.environ.get('RDB_PORT') or 28015
RDB_DBNAME = os.environ.get("RDB_DBNAME") or "iOSTest"


class Database(object):
    def __init__(self):
        conn = r.connect(RDB_HOST, RDB_PORT)
        try:
            r.db_create(RDB_DBNAME).run(conn)
            r.db(RDB_DBNAME).table_create("devices").run(conn)
            print("App database created")
        except (RqlRuntimeError, RqlDriverError):
            print("App already exists")

    def _run(self, rsql):
        try:
            c = r.connect(RDB_HOST, RDB_PORT, db=RDB_DBNAME)
            return rsql.run(c)
        except RqlDriverError:
            logger.warning("No database connection could be established!")

    def device_save(self, id: str, v: dict):
        ret = self._run(r.table("devices").get(id).update(v))
        if ret['skipped']:
            v['id'] = id
            self._run(r.table("devices").insert(v))

    def device_reset(self):
        self._run(r.table("devices").update({"status": "offline"}))


_STATUS_PREPARING = "preparing"
_STATUS_OFFLINE = "offline"
_STATUS_IDLE = "idle"


class IDevice(object):
    """ IOS Device """

    def __init__(self, udid: str, port: int, hookfunc):
        self._udid = udid
        self._port = port
        self._que = queue.Queue()
        self._hookfunc = hookfunc
        self._name = None

        self._iproxy_proc = subprocess.Popen(
            ["iproxy", str(port), "8100", udid], stdout=_DEVNULL, stderr=_DEVNULL)
        self._wdaproc = None
        self._ok = threading.Event()
        self._ok.set()
        self._output_fd = open("logs/%s-wdalog.txt" % udid, "wb")
        self._client = wda.Client("http://localhost:%d" % port)
        self._last_status = None
        self._info = {
            "udid": udid,
            "port": port,
            "status": _STATUS_PREPARING,
        }
        self.init_thread()

    @property
    def udid(self):
        return self._udid

    @property
    def name(self):
        if self._name:
            return self._name
        self._name = udid2name(self._udid)
        return self._name

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
        self._info['status'] = status
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
        logger.info("%s WDA stopped", self._udid)
        if self._wdaproc is None:
            logger.warning("%s wda is already killed", self._udid)
            return
        self._wdaproc.terminate()
        self._wdaproc = None

    def is_wda_ok(self):
        try:
            resp = self._client.status()
            self._info['ip'] = resp['ios']['ip']
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
                    self.hook(_STATUS_IDLE)
                    logger.debug("%s WDA is ready to use", self._udid)
                else:
                    self.hook(_STATUS_PREPARING)
                    logger.debug("%s WDA is still waiting", self._udid)

                    if time.time() - self._wda_started > 30:
                        logger.warning(
                            "%s WDA is down, restart after 3s", self._udid)
                        self.stop_wda()  # restart
                time.sleep(3)
            else:
                self.hook(_STATUS_OFFLINE)
                self.stop_wda()
                self._ok.wait()


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


def runcommand(*args, check=False):
    p = subprocess.run(args, capture_output=True, check=check)
    return p.stdout.strip().decode('UTF-8')


def udid2name(udid):
    try:
        return runcommand('idevicename', '-u', udid, check=True)
    except subprocess.CalledProcessError:
        return None


def list_udids():
    """
    Returns:
        list of udid
    """
    udids = runcommand('idevice_id', '-l').splitlines()
    return udids


def main():
    idevices = {}

    # stop all process
    os.setpgrp()

    def cleanup():
        os.killpg(0, signal.SIGKILL)

    atexit.register(cleanup)

    # init all
    os.makedirs("logs", exist_ok=True)
    db = Database()
    db.device_reset()

    def hookfunc(idevice, status):
        """ id, name, port, status """
        udid = idevice.udid
        info = idevice._info.copy()
        info['name'] = idevice.name or 'unknown'
        db.device_save(udid, info)
        logger.info(">>> %s [%s]", udid, status)

    last_udids = []
    while True:
        curr_udids = list_udids()
        offlines = set(last_udids).difference(curr_udids)
        onlines = set(curr_udids).difference(last_udids)
        last_udids = curr_udids

        for udid in onlines:
            port = get_device_port(udid)
            logger.info("UDID: %s came online, port: %d", udid, port)
            if udid not in idevices:
                idevices[udid] = IDevice(
                    udid, port, hookfunc)
            idevices[udid]._ok.set()

        for udid in offlines:
            logger.warning("UDID: %s went offline" % udid)
            # start iproxy and wda watch(start wda, pull status() and check if cmd finished)
            idevices[udid].set_offline()
        time.sleep(.5)


if __name__ == "__main__":
    main()
