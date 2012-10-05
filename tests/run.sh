#!/bin/bash
echo "Running master command tests"
python python/gateway/master_command_tests.py

echo "Running master communicator tests"
python python/gateway/master_communicator_tests.py

echo "Running outputs tests"
python python/gateway/outputs_tests.py

echo "Running passthrough tests"
python python/gateway/passthrough_tests.py

echo "Running users tests"
python python/gateway/users_tests.py
