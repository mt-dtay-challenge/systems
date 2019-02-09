#!/bin/bash

# Because I've wrapped this in a shell script to run task_setup, need to explicitly handle SIGINT (ctrl+c).
# Otherwise it becomes annoying to quit the container.
trap quit INT
function quit() {
    echo "Got Ctrl+C, kill the mongod so we can leave"
    kill %1
}


echo "Starting mongo"
/usr/local/bin/docker-entrypoint.sh mongod &

echo "Running task setup"
python3 task_setup.py $@

echo "Waiting for mongo"
wait
