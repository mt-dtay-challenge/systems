#!/usr/bin/env python3

from pymongo import MongoClient
import random
import logging
import sys

logging.basicConfig(format='%(asctime)s.%(msecs)03d - [%(threadName)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logging.root.setLevel(logging.INFO)

NUM_TASKS = 100 if len(sys.argv) < 2 else int(sys.argv[1])
MAX_SLEEP = 10 if len(sys.argv) < 3 else int(sys.argv[2])

def main():
    logging.info("Setting up %d tasks", NUM_TASKS)
    client = MongoClient('localhost', 27017)
    task_db = client['tasks']
    task_collection = task_db.tasks



    for i in range(NUM_TASKS):
        task = {
            'taskname': 'task-{}'.format(i),
            'sleeptime': random.randint(1, MAX_SLEEP),
            'state': 'created'
        }
        logging.info("Creating task %s", task)
        task_collection.insert_one(task)

    logging.info("All tasks created")



if __name__ == "__main__":
    main()
