import subprocess
import uuid


class Task(object):
    def __init__(self, test_name):
        self.test_name = test_name
        self.id = str(uuid.uuid1())
        self.success = None
        self.terminated = False
        self.process = None

    def run_task(self, tasks):
        try:
            self.process = subprocess.Popen(['python', '-u', 'tests/' + self.test_name + '.py'],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tasks[self.id] = self
            self.process.wait()
            if self.terminated:
                return self.id, 2
            else:
                return self.id, 0
        except Exception as e:
            return self.id, 1
