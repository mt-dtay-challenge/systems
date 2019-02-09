#!/bin/bash

set -e

if [[ -z $1 ]]; then
    echo "Usage: slave-id"
    exit 2
fi

NAME="mt-slave-$1"
LOCAL_ADDR="${NAME}:5000"
SERVER_ADDR="mt-master.tasks:5000"
DIR=$(dirname "$0")

#sudo docker build --tag mt_slave ${DIR}
sudo docker run --rm --net tasks --name $NAME mt_slave $SERVER_ADDR $LOCAL_ADDR
