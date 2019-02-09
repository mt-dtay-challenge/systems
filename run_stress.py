#!/usr/bin/env python3

import time
import threading
import random
import subprocess
from subprocess import Popen
import logging

logging.basicConfig(format='%(asctime)s.%(msecs)03d - %(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logging.root.setLevel(logging.INFO)


live_slaves = []
dead_slaves = []
next_slave_id = 0

import atexit


def start_db():
    logging.info("Starting db")
    Popen(["mongo/run.sh", '200', '5'])

def kill_db():
    logging.info("killing db")
    subprocess.run(["sudo", "docker", "rm", "--force", "mongo-srv"])

def start_new_slave():
    global next_slave_id
    slave_id = next_slave_id
    next_slave_id += 1

    def start_fn(kill_fn):
        logging.info("Starting slave %d", slave_id)
        slave_proc = Popen(["slave/run.sh", '{}'.format(slave_id)])
        return {
            'kill': kill_fn
        }

    def kill_fn():
        logging.info("Killing slave %d", slave_id)
        subprocess.run(['sudo', 'docker', 'rm', '--force', 'mt-slave-{}'.format(slave_id)])
        return {
            'restart': lambda: start_fn(kill_fn)
        }

    return start_fn(kill_fn)


def start_master():

    def start_fn(kill_fn):
        logging.info("Starting master")
        master_proc = Popen(["master/run.sh"])
        def is_done_fn():
            logging.info("Polling master to see if it is done: %s", master_proc.poll())
            return master_proc.poll() is not None

        return {
            'kill': kill_fn,
            'is_done': is_done_fn
        }

    def kill_fn():
        logging.info("Killing master")
        subprocess.run(['sudo', 'docker', 'rm', '--force', 'mt-master'])
        return {
            'restart': lambda: start_fn(kill_fn)
        }


    return start_fn(kill_fn)


def main():
    start_db()
    time.sleep(5)
    master = start_master()
    def cleanup():
        for slave in live_slaves:
            slave['kill']()
        if master is not None:
            master['kill']()
        kill_db()
    atexit.register(cleanup)
    while True:
        x = random.random()
        if x < 0.32:
            if not master:
                master = start_master()
            live_slaves.append(start_new_slave())
        elif x < 0.65:
            if len(dead_slaves) > 0:
                to_restart = random.choice(dead_slaves)
                dead_slaves.remove(to_restart)
                live_slaves.append(to_restart['restart']())
        elif x < 0.98:
            if len(live_slaves) > 0:
                slave = random.choice(live_slaves)
                live_slaves.remove(slave)
                dead_slaves.append(slave['kill']())
        else:
            if master:
                master['kill']()
                master = None

        if master and master['is_done']():
            logging.info("All is done")
            break
        time.sleep(0.5)
    

if __name__ == "__main__":
    main()
    
