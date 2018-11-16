import time


def click(s, x, y):
    print(x, y)
    s.tap(int(x * 667), int(y * 375))
    time.sleep(8)


def test(c):
    s = c.session('com.163.itest.dm75')
    time.sleep(10)

    click(s, 0.495, 0.801)
    click(s, 0.86, 0.67)
    click(s, 0.86, 0.603)
    click(s, 0.865, 0.779)
    click(s, 0.163, 0.485)
    click(s, 0.875, 0.897)
    click(s, 0.876, 0.897)

