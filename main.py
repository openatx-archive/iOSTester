from concurrent.futures import ThreadPoolExecutor

from tornado import ioloop, iostream
from tornado.web import RequestHandler, StaticFileHandler, Application

import database
from database import db, time_now
from tasks import Task

import os
import time
import threading
from queue import Queue
import queue
import rethinkdb as r


thread_pool = ThreadPoolExecutor(max_workers=1)
task_list = {}
task_queue = Queue()
test_list = []
conn = r.connect(db='iOSTest')


def on_finish(res):
    task_id, device_id, result = res.result()
    db_task = {
        'id': task_id,
        'finishedAt': time_now()
    }
    device = {
        'id': device_id,
        'status': 'idle'
    }

    if result == 0:
        db_task['result'] = 'success'
        print('{0} succeeded'.format(task_id))
    elif result == 1:
        db_task['result'] = 'fail'
        print('{0} failed'.format(task_id))
    elif result == 2:
        db_task['result'] = 'terminated'
        print('{0} terminated'.format(task_id))
    elif result == 3:
        task_list[task_id].retry = True
        task_queue.put(task_list[task_id])
        db_task['result'] = '等待重试'

    async def save_result():
        await db.task_save(db_task)
        await db.device_save(device)

    ioloop.IOLoop.current().add_callback(save_result)
    task_list.pop(task_id)


class MainHandler(RequestHandler):
    async def get(self):
        refresh_tests()
        self.render('index.html', test_list=test_list)


class StopHandler(RequestHandler):
    async def get(self, task_id):
        task_list[task_id].terminated = True
        task_list[task_id].process.terminate()


class TestHandler(RequestHandler):
    async def get(self, test_name):
        task = Task(test_name)
        if test_name not in test_list:
            self.write('Test Not Found')
            return
        db_task = {
            'id': task.id,
            'task_name': task.test_name
        }
        await db.task_save(db_task)
        task_queue.put(task)


class HistoryHandler(RequestHandler):
    async def get(self):
        tasks = []
        async for task in db.task_all():
            task['createdAt'] = task['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            if 'finishedAt' in task:
                task['finishedAt'] = task['finishedAt'].strftime('%Y-%m-%d %H:%M:%S')
            else:
                task['finishedAt'] = '暂未完成'
                task['result'] = '暂未完成'
            tasks.append(task)
        self.render('history.html', tasks=tasks)


class ReportHandler(RequestHandler):
    async def get(self, task_id):
        chunk_size = 1024*1024*2
        with open('test_reports/' + task_id + '/log.txt') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                try:
                    self.write(chunk)
                    await self.flush()
                except iostream.StreamClosedError:
                    break
                finally:
                    del chunk


current_path = os.path.dirname(__file__)

application = Application(
    [
        (r'/', MainHandler),
        (r'/([^/]+)/test', TestHandler),
        (r'/tasks/([^/]+)/stop', StopHandler),
        (r'/tasks', HistoryHandler),
        (r'/tasks/([^/]+)/report', ReportHandler)
    ],
    static_path=os.path.join(current_path, 'static'),
    template_path=os.path.join(current_path, 'templates'),
    debug=True
)


def refresh_tests():
    file_list = os.listdir('tests')
    test_list.clear()
    count = 0
    for file in file_list:
        filename_split = os.path.splitext(file)
        if filename_split[1] == '.py' and filename_split[0] != '__init__':
            test_list.append(filename_split[0])
            count += 1
    print('found {0} tests'.format(count))


class TaskManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        while True:
            try:
                found_device = False
                while not found_device:
                    for device in r.table('devices').run(conn):
                        if device['status'] == 'idle':
                            task = task_queue.get(block=True, timeout=1)
                            device['status'] = 'occupied'
                            r.table('devices').get(device['id']).update(device).run(conn)
                            if task.retry:
                                r.table('tasks').get(task.id).update({'result': '重试中'})
                            thread_pool.submit(task.run_task, task_list, device).add_done_callback(on_finish)
            except queue.Empty:
                print('no pending task')
                time.sleep(5)


if __name__ == '__main__':
    database.setup()
    refresh_tests()
    task_manager = TaskManager()
    task_manager.start()
    application.listen(9999)
    ioloop.IOLoop.instance().start()
