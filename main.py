from concurrent.futures import ThreadPoolExecutor

from tornado import ioloop
from tornado.web import RequestHandler, Application

import database
from database import db, time_now
from tasks import Task

import os
import asyncio

thread_pool = ThreadPoolExecutor()
task_list = {}
test_list = []


def on_finish(res):
    task_id, result = res.result()
    db_task = {
        'id': task_id,
        'finishedAt': time_now()
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

    async def save_result():
        await db.task_save(db_task)

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
        thread_pool.submit(task.run_task, task_list).add_done_callback(on_finish)


class HistoryHandler(RequestHandler):
    async def get(self):
        tasks = []
        async for task in db.task_all():
            task['createdAt'] = task['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            task['finishedAt'] = task['finishedAt'].strftime('%Y-%m-%d %H:%M:%S')
            tasks.append(task)
        self.render('history.html', tasks=tasks)


current_path = os.path.dirname(__file__)

application = Application(
    [
        (r'/', MainHandler),
        (r'/([^/]+)/test', TestHandler),
        (r'/tasks/([^/]+)/stop', StopHandler),
        (r'/tasks', HistoryHandler)
    ],
    static_path=os.path.join(current_path,'static'),
    template_path=os.path.join(current_path, 'templates')
)


def refresh_tests():
    file_list = os.listdir('tests')
    test_list.clear()
    count = 0
    for file in file_list:
        filename_split = os.path.splitext(file)
        if filename_split[1] == '.py':
            test_list.append(filename_split[0])
            count += 1
    print('found {0} tests'.format(count))


if __name__ == '__main__':
    database.setup()
    refresh_tests()
    application.listen(9999)
    ioloop.IOLoop.instance().start()
