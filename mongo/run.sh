#!/bin/bash

set -e

DIR=$(dirname "$0")

#sudo docker build --tag mt_mongo ${DIR}
sudo docker run --rm --net tasks --name mongo-srv mt_mongo /task_setup.sh $@
