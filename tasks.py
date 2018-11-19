import subprocess
import uuid
import os
import rethinkdb as r
import traceback

conn = r.connect(db='iOSTest')


class Task(object):
    def __init__(self, test_name):
        self.test_name = test_name
        self.id = str(uuid.uuid1())
        self.terminated = False
        self.retry = False
        self.process = None

        os.makedirs('test_reports/' + self.id, exist_ok=True)
        # os.mkdir('test_reports/' + self.id)

    def run_task(self, tasks, device):
        try:
            with open('test_reports/' + self.id + '/log.txt', 'w+') as f:
                self.process = subprocess.Popen(['python3', '-u', 'runner.py',
                                                 self.test_name, str(device['port'])],
                                                stdout=f, stderr=f)
            tasks[self.id] = self
            r.table('tasks').get(self.id).update({'device': device['name']}).run(conn)
            print('run test ' + self.id + ' on device ' + device['name'])
            self.process.wait()
            return_code = self.process.poll()
            if self.terminated:
                return self.id, device['id'], 2
            else:
                return self.id, device['id'], return_code
        except Exception as e:
            traceback.print_exc(e)
            return self.id, device['id'], 1
