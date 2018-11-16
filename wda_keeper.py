import subprocess
import wda
import time

clients = []


def wda_keeper():
    while True:
        try:
            c.status()
        except:
            subprocess.Popen(['sh', 'init.sh', uuid, port])
            time.sleep(20)


if __name__ == '__main__':

    wda_keeper()