#!/bin/bash

VERSION=${1:-latest}

(cd ../../ && tar czf src.tgz src)
mv ../../src.tgz .
cp ../../requirements.txt .

docker build -t openmotics/gateway:$VERSION .

rm src.tgz requirements.txt
