#!/bin/bash

set -e

DIR=$(dirname "$0")

sudo docker build --tag mt_mongo ${DIR}
