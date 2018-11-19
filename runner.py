import sys
import wda
from tests import *
import signal


MAX_RETRY = 3


def check_alive(c):
    try:
        c.status()
        return True
    except:
        return False


def run_test(c):
    try:
        eval(test_name).test(c)
        return 0
    except:
        is_alive = check_alive(c)
        if is_alive:
            return 1
        else:
            return 3


if __name__ == '__main__':

    retries = 0
    test_name = sys.argv[1]
    device_port = sys.argv[2]
    c = wda.Client('http://localhost:'+device_port)

    def on_close(signal, frame):
        print('terminating')
        c.session().close()

    signal.signal(signal.SIGTERM, on_close)

    result = run_test(c)

    sys.exit(result)
