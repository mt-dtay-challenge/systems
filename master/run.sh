#!/bin/bash

set -e

DIR=$(dirname "$0")

# sudo docker build --tag mt_master ${DIR}
sudo docker run --rm --net tasks --name mt-master mt_master mongodb://mongo-srv.tasks:27017/
