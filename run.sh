#!/bin/bash

# We're spawning a bunch of child processes and not bother to wait for them all or kill them nicely,
# so make sure they don't linger.
trap "exit" INT TERM
trap "kill 0" EXIT

# Clean up logs
rm -fv *.log.*

echo "*** Starting up"
mongo/run.sh 100 10 >& mongo.log.1 &
sleep 10

master/run.sh >& master.log.1 &
tail -F master.log.1 &
slave/run.sh 1 >& slave-1.log.1 &
tail -F slave-1.log.1 &
slave/run.sh 2 >& slave-2.log.1 &
tail -F slave-2.log.1 &
slave/run.sh 3 >& slave-3.log.1 &
tail -F slave-3.log.1 &

echo "*** Letting things run for a bit"

sleep 30

echo "*** Killing slave 1"
sudo docker rm mt-slave-1 --force

sleep 30

echo "*** Killing master"
sudo docker rm mt-master --force

sleep 10

echo "*** Killing slave 3"
sudo docker rm mt-slave-3 --force

sleep 10

echo "*** Restarting master"
master/run.sh >& master.log.2 &
MASTER_PID=$!
tail -F master.log.2 &


sleep 20
echo "Restarting slave 3"
slave/run.sh 3 >& slave-3.log.2 &
tail -F slave-3.log.2 &


sleep 20
echo "Restarting slave 1"
slave/run.sh 1 >& slave-1.log.2 &
tail -F slave-1.log.2 &

echo "Waiting for master to finish"
wait $MASTER_PID
echo "Master completed, we should be finished, clean up a bit"
sudo docker rm mt-slave-1 --force
sudo docker rm mt-slave-2 --force
sudo docker rm mt-slave-3 --force
sudo docker rm mongo-srv --force

# Kill off all the tails
pkill -P $$
