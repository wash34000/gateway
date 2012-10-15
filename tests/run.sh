#!/bin/bash
cd python

echo "Running master command tests"
python gateway/master_command_tests.py

echo "Running master communicator tests"
python gateway/master_communicator_tests.py

echo "Running outputs tests"
python gateway/outputs_tests.py

echo "Running passthrough tests"
python gateway/passthrough_tests.py

echo "Running users tests"
python gateway/users_tests.py
