import subprocess
import uuid
import os


class Task(object):
    def __init__(self, test_name):
        self.test_name = test_name
        self.id = str(uuid.uuid1())
        self.device = 'None'
        self.success = None
        self.terminated = False
        self.process = None
        os.mkdir('test_reports/' + self.id)

    def run_task(self, tasks, devices):
        found_device = False
        while not found_device:
            for device in devices:
                if devices[device]['status'] == 'idle':
                    found_device = True
                    try:
                        with open('test_reports/' + self.id + '/log.txt', 'w+') as f:
                            self.process = subprocess.Popen(['python3', '-u', 'runner.py',
                                                             self.test_name, devices[device]['port']],
                                                            stdout=f, stderr=f)
                        tasks[self.id] = self
                        tasks[self.id].device = device
                        devices[device]['status'] = 'occupied'
                        print('run test ' + self.id + ' on device ' + devices[device]['name'])
                        self.process.wait()
                        return_code = self.process.poll()
                        if self.terminated:
                            return self.id, device, 2
                        else:
                            return self.id, device, return_code
                    except:
                        return self.id, device, 1
