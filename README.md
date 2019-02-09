# Systems Challenge

## High-level Scripts
High level scripts are provided to build and run the whole process, and/or start the individual containers with convenient default parameters.

```
./setup.sh:       Creates the docker network (tasks) and builds the 3 docker images
./run.sh:         Runs mongo, master, and 3 slave instances, killing and restarting them in the middle.  Terminates when all tasks are complete.
./run_stress.py:  Similar to run.sh, but with 200 tasks, and kills/restarts/news happening randomly every half second.

master/run.sh:    Starts a master container.
slave/run.sh:     [slave_id]: Starts a slave container with the specified id.
mongo/run.sh [num_tasks] [max_sleep]: Starts a mongo container, and runs the task setup script inside of it to prepopulate a set of tasks.
```


## Approach
### Communication
Using a docker network named "tasks" to communicate between containers.

Master is launched with the mongo URI

Slaves are launched with the master URI

Master and slaves communicate with each other via HTTP.

### Kill Detection
Master runs a regular health check of all known slaves - both those that have explicitly connected since restart, and those that are marked as currently running a task in the db.

If a slave cannot be reached, it is assumed to have been killed, and any currently assigned task is marked as killed and added back to the queue for rescheduling.

In the case of connectivity issues between containers, this might not be ideal behavior, depending on the cost and idempotency of the tasks being run.

### Fault Tolerance Cases
#### Master dies
Slaves will retry sending their task completion messages forever.

On master restart, it will reload task states from the DB.

#### Slave dies
Master will notice via healthcheck that it has gone, mark its tasks as killed, and reschedule them later

If the slave dies and restarts in-between healthchecks, master will receive a 'connect' message from it and assume it died (again marking its tasks as killed and rescheduling).

#### Master dies, slave completes task but dies before master restarts
Master will reload with task in 'running' status.
If slave reconnects before healthcheck, master will assume slave died and reschedule task.
If slave remains dead, master will healthcheck, which will fail, and reschedule task.


#### Master distributes final task, slave dies before completion
Task gets marked as killed, gets returned to the queue and rescheduled by master

#### Master sends task, but dies before recording it to db
On restart, master will reschedule the task


## Log Analysis
I've cherry-picked some of the logs below to highlight the key points of operations.  See combined.log for the full merged log.  The per-container logs are also available as separate files.

### Startup
On startup we can see that there are 100 tasks remaining, and that slaves are connecting.
```
02/09/2019 08:12:41.752 - master.py - [Thread-1] Received new connection from mt-slave-1:5000
02/09/2019 08:12:41.753 - master.py - [Thread-1] Setting up client API with prefix http://mt-slave-1:5000/
02/09/2019 08:12:42.448 - master.py - [Thread-2] Received new connection from mt-slave-3:5000
02/09/2019 08:12:42.448 - master.py - [Thread-2] Setting up client API with prefix http://mt-slave-3:5000/
02/09/2019 08:12:43.023 - master.py - [Thread-3] Received new connection from mt-slave-2:5000
02/09/2019 08:12:43.023 - master.py - [Thread-3] Setting up client API with prefix http://mt-slave-2:5000/
02/09/2019 08:12:43.419 - master.py - [health] 100 tasks not yet complete
02/09/2019 08:12:43.419 - master.py - [health] Running healthcheck against 3 slaves
```

### Normal Operation
At the start we can see that tasks are being handed out and completed by the slaves.
```
02/09/2019 08:12:41.753 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342e66799100081b245a'), 'taskname': 'task-0', 'state': 'created', 'sleeptime': 6} to slave {'remote_addr': 'mt-slave-1:5000', 'api': <__main__.ClientApi object at 0x7fc940196208>}
02/09/2019 08:12:41.834 - mt-slave-1:5000 - [Thread-1] Received task task-0, will sleep for 6 seconds
02/09/2019 08:12:41.835 - mt-slave-1:5000 - [taskrunner] Sleeping for 6 seconds
02/09/2019 08:12:41.837 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b245b'), 'taskname': 'task-1', 'state': 'created', 'sleeptime': 3}, finding next slave
02/09/2019 08:12:42.449 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b245b'), 'taskname': 'task-1', 'state': 'created', 'sleeptime': 3} to slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7fc94018aeb8>}
02/09/2019 08:12:42.451 - mt-slave-3:5000 - [Thread-1] Received task task-1, will sleep for 3 seconds
02/09/2019 08:12:42.451 - mt-slave-3:5000 - [taskrunner] Sleeping for 3 seconds
02/09/2019 08:12:42.453 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b245c'), 'taskname': 'task-2', 'state': 'created', 'sleeptime': 7}, finding next slave
02/09/2019 08:12:43.024 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b245c'), 'taskname': 'task-2', 'state': 'created', 'sleeptime': 7} to slave {'remote_addr': 'mt-slave-2:5000', 'api': <__main__.ClientApi object at 0x7fc94216aba8>}
02/09/2019 08:12:43.031 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b245d'), 'taskname': 'task-3', 'state': 'created', 'sleeptime': 1}, finding next slave
02/09/2019 08:12:43.419 - master.py - [health] 100 tasks not yet complete
02/09/2019 08:12:43.419 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:12:43.017 - mt-slave-2:5000 - [MainThread] Connecting to server at http://mt-master.tasks:5000/connect/mt-slave-2:5000
02/09/2019 08:12:43.028 - mt-slave-2:5000 - [Thread-1] Received task task-2, will sleep for 7 seconds
02/09/2019 08:12:43.028 - mt-slave-2:5000 - [taskrunner] Sleeping for 7 seconds
02/09/2019 08:12:45.437 - master.py - [health] 100 tasks not yet complete
02/09/2019 08:12:45.438 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:12:45.452 - mt-slave-3:5000 - [taskrunner] Sleeping done for task-1, notifying server
02/09/2019 08:12:45.454 - master.py - [Thread-4] Marking task-1 as success
02/09/2019 08:12:45.455 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b245d'), 'taskname': 'task-3', 'state': 'created', 'sleeptime': 1} to slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7fc94018aeb8>}
02/09/2019 08:12:45.458 - mt-slave-3:5000 - [Thread-4] Received task task-3, will sleep for 1 seconds
02/09/2019 08:12:45.458 - mt-slave-3:5000 - [taskrunner] Sleeping for 1 seconds
02/09/2019 08:12:45.460 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b245e'), 'taskname': 'task-4', 'state': 'created', 'sleeptime': 7}, finding next slave
02/09/2019 08:12:46.459 - mt-slave-3:5000 - [taskrunner] Sleeping done for task-3, notifying server
02/09/2019 08:12:46.462 - master.py - [Thread-5] Marking task-3 as success
02/09/2019 08:12:46.463 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b245e'), 'taskname': 'task-4', 'state': 'created', 'sleeptime': 7} to slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7fc94018aeb8>}
02/09/2019 08:12:46.466 - mt-slave-3:5000 - [Thread-5] Received task task-4, will sleep for 7 seconds
02/09/2019 08:12:46.466 - mt-slave-3:5000 - [taskrunner] Sleeping for 7 seconds
02/09/2019 08:12:46.468 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b245f'), 'taskname': 'task-5', 'state': 'created', 'sleeptime': 2}, finding next slave
02/09/2019 08:12:47.454 - master.py - [health] 98 tasks not yet complete
```


### Slave 1 killed
Slave 1 was in the process of task 10, which is marked as killed upon detection.
```
02/09/2019 08:12:59.881 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b2464'), 'taskname': 'task-10', 'state': 'created', 'sleeptime': 10} to slave {'remote_addr': 'mt-slave-1:5000', 'api': <__main__.ClientApi object at 0x7fc940196208>}
02/09/2019 08:12:59.885 - mt-slave-1:5000 - [Thread-13] Received task task-10, will sleep for 10 seconds
02/09/2019 08:12:59.887 - mt-slave-1:5000 - [taskrunner] Sleeping for 10 seconds
02/09/2019 08:13:07.609 - mt-slave-2:5000 - [Thread-17] 172.18.0.4 - - [09/Feb/2019 20:13:07] "GET /status HTTP/1.1" 200 -
*** Killing slave 1
02/09/2019 08:13:09.614 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:13:09.615 - master.py - [health] Assuming slave {'remote_addr': 'mt-slave-1:5000', 'api': <__main__.ClientApi object at 0x7fc940196208>} is dead, marking any task as killed
02/09/2019 08:13:09.616 - master.py - [health] Marked {'_id': ObjectId('5c5f342f66799100081b2464'), 'taskname': 'task-10', 'state': 'running', 'sleeptime': 10, 'host': 'mt-slave-1:5000'} as killed, adding back to queue
```

Next time master restarts, we see it is still in state killed.  It is then rescheduled and completed fully.
```
02/09/2019 08:14:03.661 - master.py - [MainThread] Loading task {'_id': ObjectId('5c5f342f66799100081b2464'), 'taskname': 'task-10', 'state': 'killed', 'sleeptime': 10, 'host': 'mt-slave-1:5000'} in state killed

# It is rescheduled, and completes fully later
02/09/2019 08:14:04.664 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b2464'), 'taskname': 'task-10', 'state': 'killed', 'sleeptime': 10, 'host': 'mt-slave-1:5000'} to slave {'remote_addr': 'mt-slave-2:5000', 'api': <__main__.ClientApi object at 0x7f573d02a320>}

02/09/2019 08:14:04.667 - mt-slave-2:5000 - [Thread-41] Received task task-10, will sleep for 10 seconds
02/09/2019 08:14:14.679 - mt-slave-2:5000 - [taskrunner] Sleeping done for task-10, notifying server
02/09/2019 08:14:14.684 - master.py - [Thread-2] Marking task-10 as success
```


### Master and Slave 3 killed
While master is down, slaves 2 and 3 complete their tasks, and start retry-looping to notify of completion.
```
*** Killing master
mt-master
02/09/2019 08:13:43.582 - mt-slave-3:5000 - [taskrunner] Sleeping done for task-23, notifying server
02/09/2019 08:13:43.690 - mt-slave-3:5000 - [taskrunner] Failed to send task completion to master, will retry
02/09/2019 08:13:44.764 - mt-slave-3:5000 - [taskrunner] Failed to send task completion to master, will retry
02/09/2019 08:13:49.168 - mt-slave-2:5000 - [taskrunner] Sleeping done for task-24, notifying server
02/09/2019 08:13:49.223 - mt-slave-2:5000 - [taskrunner] Failed to send task completion to master, will retry
02/09/2019 08:13:50.091 - mt-slave-3:5000 - [taskrunner] Failed to send task completion to master, will retry
*** Killing slave 3
```

On master restart, both pending tasks are loaded from the db as "running"
```
02/09/2019 08:14:03.662 - master.py - [MainThread] Loading task {'_id': ObjectId('5c5f342f66799100081b2471'), 'taskname': 'task-23', 'state': 'running', 'sleeptime': 6, 'host': 'mt-slave-3:5000'} in state running
02/09/2019 08:14:03.662 - master.py - [MainThread] Already running on host mt-slave-3:5000, tracking it
02/09/2019 08:14:03.662 - master.py - [MainThread] Setting up client API with prefix http://mt-slave-3:5000/
02/09/2019 08:14:03.662 - master.py - [MainThread] Loading task {'_id': ObjectId('5c5f342f66799100081b2472'), 'taskname': 'task-24', 'state': 'running', 'sleeptime': 9, 'host': 'mt-slave-2:5000'} in state running
02/09/2019 08:14:03.663 - master.py - [MainThread] Already running on host mt-slave-2:5000, tracking it
```

Slave 3 is still down, master detects its pending task as killed and reschedules it
```

02/09/2019 08:14:03.682 - master.py - [health] Assuming slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7f573d02a208>} is dead, marking any task as killed
02/09/2019 08:14:03.683 - master.py - [health] Marked {'_id': ObjectId('5c5f342f66799100081b2471'), 'taskname': 'task-23', 'state': 'running', 'sleeptime': 6, 'host': 'mt-slave-3:5000'} as killed, adding back to queue
```

Slave 2, which has been up this whole time, notifies the new master of completion of its task and receives its next one.
```
02/09/2019 08:14:04.662 - master.py - [Thread-1] Marking task-24 as success
02/09/2019 08:14:04.664 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b2464'), 'taskname': 'task-10', 'state': 'killed', 'sleeptime': 10, 'host': 'mt-slave-1:5000'} to slave {'remote_addr': 'mt-slave-2:5000', 'api': <__main__.ClientApi object at 0x7f573d02a320>}
02/09/2019 08:14:04.667 - mt-slave-2:5000 - [Thread-41] Received task task-10, will sleep for 10 seconds
```

Slave 3 comes back, starts getting new tasks.
```
02/09/2019 08:14:24.560 - master.py - [Thread-3] Received new connection from mt-slave-3:5000
02/09/2019 08:14:24.560 - master.py - [Thread-3] Setting up client API with prefix http://mt-slave-3:5000/
02/09/2019 08:14:24.560 - _internal.py - [Thread-3] 172.18.0.4 - - [09/Feb/2019 20:14:24] "POST /connect/mt-slave-3:5000 HTTP/1.1" 200 -
02/09/2019 08:14:24.561 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b2474'), 'taskname': 'task-26', 'state': 'created', 'sleeptime': 2} to slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7f5735fc7828>}
02/09/2019 08:14:24.564 - mt-slave-3:5000 - [Thread-1] Received task task-26, will sleep for 2 seconds
```

Slave 1 later also comes back, and starts getting new tasks.
```
02/09/2019 08:14:44.544 - master.py - [Thread-10] Received new connection from mt-slave-1:5000
02/09/2019 08:14:44.544 - master.py - [Thread-10] Setting up client API with prefix http://mt-slave-1:5000/
02/09/2019 08:14:44.544 - _internal.py - [Thread-10] 172.18.0.5 - - [09/Feb/2019 20:14:44] "POST /connect/mt-slave-1:5000 HTTP/1.1" 200 -
02/09/2019 08:14:44.545 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b247b'), 'taskname': 'task-33', 'state': 'created', 'sleeptime': 7} to slave {'remote_addr': 'mt-slave-1:5000', 'api': <__main__.ClientApi object at 0x7f5735fbddd8>}
02/09/2019 08:14:44.547 - mt-slave-1:5000 - [Thread-1] Received task task-33, will sleep for 7 seconds
```

Everything then proceeds healthily to completion.  Note that the last task is previously-killed task-23, which slave-3 had done but died before it could tell master about.

```
02/09/2019 08:16:34.811 - master.py - [taskrunner] Next task is {'_id': ObjectId('5c5f342f66799100081b2471'), 'taskname': 'task-23', 'state': 'killed', 'sleeptime': 6, 'host': 'mt-slave-3:5000'}, finding next slave
02/09/2019 08:16:34.908 - mt-slave-3:5000 - [taskrunner] Sleeping done for task-97, notifying server
02/09/2019 08:16:34.911 - master.py - [Thread-77] Marking task-97 as success
02/09/2019 08:16:34.912 - master.py - [taskrunner] Sending task {'_id': ObjectId('5c5f342f66799100081b2471'), 'taskname': 'task-23', 'state': 'killed', 'sleeptime': 6, 'host': 'mt-slave-3:5000'} to slave {'remote_addr': 'mt-slave-3:5000', 'api': <__main__.ClientApi object at 0x7f5735fc7828>}
02/09/2019 08:16:34.915 - mt-slave-3:5000 - [Thread-93] Received task task-23, will sleep for 6 seconds
02/09/2019 08:16:34.916 - mt-slave-3:5000 - [taskrunner] Sleeping for 6 seconds
02/09/2019 08:16:35.085 - master.py - [Thread-78] Marking task-98 as success
02/09/2019 08:16:35.082 - mt-slave-2:5000 - [taskrunner] Sleeping done for task-98, notifying server
02/09/2019 08:16:36.767 - master.py - [health] 2 tasks not yet complete
02/09/2019 08:16:36.768 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:16:38.780 - master.py - [health] 2 tasks not yet complete
02/09/2019 08:16:38.780 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:16:40.798 - master.py - [health] 2 tasks not yet complete
02/09/2019 08:16:40.798 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:16:40.920 - mt-slave-3:5000 - [taskrunner] Sleeping done for task-23, notifying server
02/09/2019 08:16:40.923 - master.py - [Thread-79] Marking task-23 as success
02/09/2019 08:16:42.813 - master.py - [health] 1 tasks not yet complete
02/09/2019 08:16:42.813 - master.py - [health] Running healthcheck against 3 slaves
02/09/2019 08:16:42.816 - mt-slave-1:5000 - [taskrunner] Sleeping done for task-99, notifying server
02/09/2019 08:16:42.819 - master.py - [Thread-80] Marking task-99 as success
02/09/2019 08:16:44.829 - master.py - [health] 0 tasks not yet complete
02/09/2019 08:16:44.830 - master.py - [MainThread] Done!

```
