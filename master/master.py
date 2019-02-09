#!/usr/bin/env python3

from flask import Flask
from pymongo import MongoClient
import random
import logging
from enum import Enum
import requests
from queue import Queue
import time
import json
import threading
import sys

if len(sys.argv) != 2:
    print("Usage: db-uri")
    sys.exit(2)

logging.basicConfig(format='%(asctime)s.%(msecs)03d - %(filename)s - [%(threadName)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logging.root.setLevel(logging.INFO)

class TaskState(Enum):
    Created='created'
    Running='running'
    Killed='killed'
    Success='success'

CLIENT_HEALTH_TIMEOUT_SECONDS = 1
CLIENT_SEND_TASK_TIMEOUT_SECONDS = 1
HEALTH_CHECK_MIN_INTERVAL_SECONDS = 2

class ClientApi:
    def __init__(self, addr):
        self.addr = addr
        self.prefix = 'http://{}/'.format(addr)
        logging.info("Setting up client API with prefix %s", self.prefix)

    def get_status(self):
        url = self.prefix + 'status'
        try:
            requests.get(url, timeout=CLIENT_HEALTH_TIMEOUT_SECONDS)
            return True
        except requests.exceptions.RequestException as e:
            return False

    def send_task(self, task):
        url = self.prefix + 'run_task'
        data = {
                'taskname': task['taskname'],
                'sleeptime': task['sleeptime']
                }
        requests.post(url, data=json.dumps(data), timeout=CLIENT_SEND_TASK_TIMEOUT_SECONDS)
    

class Server:
    def __init__(self):
        client = MongoClient(sys.argv[1])
        task_db = client['tasks']
        task_collection = task_db.tasks
        self.tasks = task_collection
        self.queued_tasks = Queue()
        self.slaves = {}
        self.idle_slaves = Queue()
        self.done = False

        for task in task_collection.find():
            state = task['state']
            logging.info("Loading task %s in state %s", task, state)
            if state == TaskState.Created.value or state == TaskState.Killed.value:
                logging.info("Needs to be re-run, queueing")
                self.queued_tasks.put(task)
            elif state == TaskState.Running.value:
                logging.info("Already running on host %s, tracking it", task['host'])
                # Make sure we track the host running it, so we can see if it has died.
                if task['host'] not in self.slaves:
                    self.create_slave(task['host'])
            elif state == TaskState.Success.value:
                logging.info("Already completed")
            else:
                logging.error("Unknown task state: %s", state)


        self.setup_server()

    def create_slave(self, remote_addr):
        self.slaves[remote_addr] = {
                'remote_addr': remote_addr,
                'api': ClientApi(remote_addr)
                }

    def setup_server(self):
        app = Flask("Master")
        self.app = app

        @app.route('/connect/<path:remote_addr>', methods=['POST'])
        def connect(remote_addr):
            logging.info("Received new connection from %s", remote_addr)
            if remote_addr in self.slaves:
                logging.warning("We thought we already knew this client, assume it died.")
                self.assume_dead(self.slaves[remote_addr])
            self.create_slave(remote_addr)
            self.idle_slaves.put(self.slaves[remote_addr])
            return ""

        @app.route('/complete/<path:remote_addr>/<path:taskname>', methods=['POST'])
        def complete_task(remote_addr, taskname):
            logging.info("Marking %s as success", taskname)
            self.tasks.update_one(
                    { 'taskname': taskname },
                    { '$set': { 'state': TaskState.Success.value } }
                    )

            if remote_addr not in self.slaves:
                logging.info("Rediscovered %s", remote_addr)
                self.create_slave(remote_addr)

            self.idle_slaves.put(self.slaves[remote_addr])
            return ""

    def send_task(self, task, slave):
        logging.info("Sending task %s to slave %s", task, slave)
        slave['api'].send_task(task)
        self.tasks.update_one(
                { 'taskname': task['taskname'] },
                { '$set': {
                    'host': slave['remote_addr'],
                    'state': TaskState.Running.value
                    }
                }
            )

    def get_available_slave(self):
        return self.idle_slaves.get()
    
    def assume_dead(self, slave):
        logging.info("Assuming slave %s is dead, marking any task as killed", slave)
        dead_filter = { '$and': [
                 { 'host': slave['remote_addr'] },
                 {'state': TaskState.Running.value }
                ]}
        dead_task = self.tasks.find_one_and_update(dead_filter,
                { '$set': { 'state': TaskState.Killed.value } }
                )
        del self.slaves[slave['remote_addr']]
        if dead_task is not None:
            logging.info("Marked %s as killed, adding back to queue", dead_task)
            dead_task['state'] = TaskState.Killed.value
            self.queued_tasks.put(dead_task)
        else:
            logging.info("Wasn't running any tasks")
    
    def check_if_done(self):
        remaining_tasks = list(self.tasks.find({'state': { '$ne': TaskState.Success.value } }))
        logging.info("%d tasks not yet complete", len(remaining_tasks))
        if len(remaining_tasks) == 0:
            self.done = True

    def health_loop(self):
        while not self.done:
            logging.info("Running healthcheck against %d slaves", len(self.slaves))
            slaves = list(self.slaves.values())
            for slave in slaves:
                if not slave['api'].get_status():
                    self.assume_dead(slave)
            time.sleep(HEALTH_CHECK_MIN_INTERVAL_SECONDS)

            self.check_if_done()

    def run_tasks(self):
        while not self.done:
            task = self.queued_tasks.get()
            logging.info("Next task is %s, finding next slave", task)
            while True:
                try:
                    slave = self.get_available_slave()
                    self.send_task(task, slave)
                    break
                except requests.exceptions.RequestException as e:
                    logging.error("Couldn't send task to slave, retry")


    def run(self):
        http_thread = threading.Thread(target=lambda: self.app.run(host='0.0.0.0'), name='http')
        health_thread = threading.Thread(target=lambda: self.health_loop(), name='health')
        tasks_thread = threading.Thread(target=lambda: self.run_tasks(), name='taskrunner')
        threads = [
                http_thread,
                health_thread,
                tasks_thread
                ]
        for thread in threads:
            thread.daemon = True
            thread.start()

        health_thread.join()

        logging.info("Done!")

def main():
    s = Server()
    s.run()

if __name__ == "__main__":
    main()
