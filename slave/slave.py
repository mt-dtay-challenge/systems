#!/usr/bin/env python3

from flask import Flask
from flask import request
import logging
import sys
import time
import requests
from queue import Queue
import threading
import time

if len(sys.argv) != 3:
    print("Usage: server_addr local_addr")
    sys.exit(2)

server_addr = sys.argv[1]
local_addr = sys.argv[2]
tasks = Queue(1)
logging.basicConfig(format='%(asctime)s.%(msecs)03d - {} - [%(threadName)s] %(message)s'.format(local_addr), datefmt='%m/%d/%Y %I:%M:%S')
logging.root.setLevel(logging.INFO)

SERVER_TIMEOUT_SECONDS=2

app = Flask("Slave")

class ServerApi:
    def __init__(self, server_addr, local_addr):
        self.server_addr = server_addr
        self.local_addr = local_addr
        self.prefix = 'http://{}/'.format(server_addr)
        logging.info("Setting up server with prefix %s", self.prefix)

    def connect(self):
        url = self.prefix + 'connect/' + self.local_addr
        logging.info("Connecting to server at %s", url)
        while True:
            try:
                requests.post(url, timeout=SERVER_TIMEOUT_SECONDS)
                return
            except requests.exceptions.RequestException as e:
                logging.error("Failed to connect to master, will retry")
                time.sleep(1)

    def complete(self, taskname):
        url = self.prefix + 'complete/{}/{}'.format(self.local_addr, taskname)
        while True:
            try:
                requests.post(url, timeout=SERVER_TIMEOUT_SECONDS)
                return
            except requests.exceptions.RequestException as e:
                logging.error("Failed to send task completion to master, will retry")
                time.sleep(1)

api = ServerApi(server_addr, local_addr)

def sleeper():
    while True:
        task = tasks.get()
        sleep_time, taskname = task['sleeptime'], task['taskname']
        logging.info("Sleeping for %d seconds", sleep_time)
        time.sleep(sleep_time)
        logging.info("Sleeping done for %s, notifying server", taskname)
        api.complete(taskname)


@app.route('/status')
def status():
    return "OK"

@app.route('/run_task', methods=['POST'])
def run_task():
    task = request.get_json(force=True)
    logging.info("Received task %s, will sleep for %d seconds", task['taskname'], task['sleeptime'])
    tasks.put(task)

    return "OK"

http_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0'), name='http')
task_thread = threading.Thread(target=sleeper, name='taskrunner')
http_thread.daemon = True
task_thread.daemon = True
http_thread.start()
task_thread.start()
time.sleep(1)
api.connect()
task_thread.join()
http_thread.join()
