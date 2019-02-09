#!/bin/bash

sudo docker network create tasks
mongo/build.sh
master/build.sh
slave/build.sh
