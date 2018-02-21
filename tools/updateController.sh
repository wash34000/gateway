#!/bin/bash

if [ $# -ne 4 ]; then
    echo Usage: $0 hw_version pic_version hex_file old_hex_file
    exit 2
fi

OPEN_MOTICS_PATH=/opt/openmotics

HW=$1
PIC=$2
HEX_FILE=$3
OLD_HEX_FILE=$4
PORT=`python $OPEN_MOTICS_PATH/python/master_tool.py --port`

function status {
    echo "$1" >> /opt/openmotics/update_status
}

function sync_serial {
    for i in `seq 0 5`; do
        python $OPEN_MOTICS_PATH/python/master_tool.py --sync
        if [ "$?" == "0" ]; then
            return 0
        fi
    done
    return 1
}

function flash {
    status "Flashing the master"
    $OPEN_MOTICS_PATH/bin/AN1310cl -d $PORT -b 115200 -p -c $1
    if [ "$?" == "0" ]; then
        status "Verifying master firmware"
        $OPEN_MOTICS_PATH/bin/AN1310cl -d $PORT -b 115200 -v $1
        if [ "$?" == "0" ]; then
            return 0
        fi
    fi
    return 1
}

## Reset the controller
status "Syncing the master"
sync_serial
if [ "$?" != "0" ]; then
    echo Could not sync with the master.
    exit 1
fi

hw_version=`python $OPEN_MOTICS_PATH/python/master_tool.py --version | awk '{ print $2; }'`
if [ "$hw_version" == "$HW" ]; then
    ## Go into the bootloader
    status "Resetting the master"
    python $OPEN_MOTICS_PATH/python/master_tool.py --reset
    $OPEN_MOTICS_PATH/bin/AN1310cl -d $PORT -b 115200 -a
    ## Check the PIC version
    hardware=`$OPEN_MOTICS_PATH/bin/AN1310cl -d $PORT -b 115200 -s | tail -n 1 | awk '{ print $1; }'`

    if [ "$hardware" == "$PIC" ]; then
        ## Flash the controller
        success=TRUE
        flash $HEX_FILE
        # Revert to the old version if the flash failed
        if [ "$?" != "0" ]; then
            echo " ================================="
            echo " Error while flashing or verifying"
            echo " ================================="
            flash $OLD_HEX_FILE
            success=FALSE
        fi
    else
        echo " ==================================================================="
        echo " The hardware PIC ($hardware) does not match the required PIC ($PIC)"
        echo " ==================================================================="
        success=FALSE
    fi

    ## Kick the bootloader to start the firmware
    $OPEN_MOTICS_PATH/bin/AN1310cl -d $PORT -b 115200 -r
    sleep 1
else
    echo " ===================================================================================="
    echo "The hardware version ($hw_version) does not match the required hardware version ($HW)"
    echo " ===================================================================================="
    success=FALSE
fi

sync_serial

if [ "$success" == "TRUE" ]; then
    exit 0
else
    exit 1
fi
