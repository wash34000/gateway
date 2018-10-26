#!/bin/bash

docker run -p 8443:443 -e FORCE_PYOPENSSL="True" -v $(pwd)/../plugin_runtime:/opt/plugin_runtime -it openmotics/gateway:latest
