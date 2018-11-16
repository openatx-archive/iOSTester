import sys
import wda
from tests import *
import time
import signal


MAX_RETRY = 3


def check_alive(c):
    try:
        c.status()
        return True
    except:
        return False


def run_test(c, retries):
    try:
        eval(test_name).test(c)
        return True
    except:
        is_alive = check_alive(c)
        if retries == 3:
            return False
        elif not is_alive:
            time.sleep(30)
            run_test(c, retries+1)
        else:
            return False


if __name__ == '__main__':

    retries = 0
    test_name = sys.argv[1]
    device_port = sys.argv[2]
    c = wda.Client('http://localhost:'+device_port)

    def on_close(signal, frame):
        print('terminating')
        c.session().close()

    signal.signal(signal.SIGTERM, on_close)

    result = run_test(c, 0)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)
