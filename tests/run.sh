#!/bin/bash
cd python

echo "Running master api tests"
python -m master.master_api_tests

echo "Running master command tests"
python -m master.master_command_tests

echo "Running master communicator tests"
python -m master.master_communicator_tests

echo "Running outputs tests"
python -m master.outputs_tests

echo "Running inputs tests"
python -m master.inputs_tests

echo "Running passthrough tests"
python -m master.passthrough_tests

echo "Running thermostats tests"
python -m master.thermostats_tests

echo "Running users tests"
python -m gateway.users_tests

echo "Running power controller tests"
python -m power.power_controller_tests

echo "Running power communicator tests"
python -m power.power_communicator_tests

echo "Running time keeper tests"
python -m power.time_keeper_tests
