#!/bin/bash

CUR_DIR=`pwd`

## Create the openmotics directory
mkdir -p /opt/openmotics/bin
mkdir -p /opt/openmotics/etc
mkdir -p /opt/openmotics/lib
mkdir -p /opt/openmotics/download

## Install pyserial
opkg update
opkg install python-pyserial

## Copy our software
cp -R Utilities/* /opt/openmotics/lib/
cp -R OpenMoticsService /opt/openmotics/
cp -R VpnService /opt/openmotics/
cp -R UpdateService /opt/openmotics/
touch /opt/openmotics/etc/blacklist

cp Tools/* /opt/openmotics/bin

## Disable the unnecessary services
systemctl disable bone101.service
systemctl disable cloud9.service
systemctl disable gateone.service

## Install OpenVPN
wget http://swupdate.openvpn.org/community/releases/openvpn-2.2.2.tar.gz
tar xzf openvpn-2.2.2.tar.gz
cd openvpn-2.2.2
./configure
make
make install

## Install supervisord
opkg install python-setuptools python-compile python-core python-crypt python-io python-lang \
    python-misc python-netclient python-netserver python-pprint python-profile python-re \
    python-shell python-stringold python-threading python-unixadmin python-xmlrpc python-crypt \
    python-datetime python-fcntl python-unixadmin python-readline python-resource python-zlib \
    python-ctypes python-dbus

wget http://pypi.python.org/packages/source/s/supervisor/supervisor-3.0a12.tar.gz#md5=eb2ea5a2c3b665ba9277d17d14584a25
tar xzf supervisor-3.0a12.tar.gz#md5\=eb2ea5a2c3b665ba9277d17d14584a25
cd supervisor-3.0a12
python setup.py install

mkdir /etc/supervisor/
mkdir /etc/supervisor/conf.d/
mkdir /var/log/supervisor/
cat << EOF > /etc/supervisord.conf
; supervisor config file

[unix_http_server]
file=/var/run//supervisor.sock   ; (the path to the socket file)
chmod=0700                       ; sockef file mode (default 0700)

[supervisord]
logfile=/var/log/supervisor/supervisord.log ; (main log file;default $CWD/supervisord.log)
pidfile=/var/run/supervisord.pid ; (supervisord pidfile;default supervisord.pid)
childlogdir=/var/log/supervisor            ; ('AUTO' child log dir, default $TEMP)

; the below section must remain in the config file for RPC
; (supervisorctl/web interface) to work, additional interfaces may be
; added by defining them in separate rpcinterface: sections
[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///var/run//supervisor.sock ; use a unix:// URL  for a unix socket

; The [include] section can just contain the "files" setting.  This
; setting can list multiple files (separated by whitespace or
; newlines).  It can also contain wildcards.  The filenames are
; interpreted as relative to this file.  Included files *cannot*
; include files themselves.

[include]
files = /etc/supervisor/conf.d/*.conf
EOF

cat << EOF > /etc/init.d/supervisor
#! /bin/sh
#
# skeleton  example file to build /etc/init.d/ scripts.
#           This file should be used to construct scripts for /etc/init.d.
#
#           Written by Miquel van Smoorenburg <miquels@cistron.nl>.
#           Modified for Debian
#           by Ian Murdock <imurdock@gnu.ai.mit.edu>.
#               Further changes by Javier Fernandez-Sanguino <jfs@debian.org>
#
# Version:  @(#)skeleton  1.9  26-Feb-2001  miquels@cistron.nl
#
### BEGIN INIT INFO
# Provides:          supervisor
# Required-Start:    \$remote_fs \$network \$named
# Required-Stop:     \$remote_fs \$network \$named
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start/stop supervisor
# Description:       Start/stop supervisor daemon and its configured
#                    subprocesses.
### END INIT INFO


PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
DAEMON=/usr/bin/supervisord
NAME=supervisord
DESC=supervisor

test -x \$DAEMON || exit 0

LOGDIR=/var/log/supervisor
PIDFILE=/var/run/\$NAME.pid
DODTIME=5                   # Time to wait for the server to die, in seconds
                            # If this value is set too low you might not
                            # let some servers to die gracefully and
                            # 'restart' will not work

# Include supervisor defaults if available
if [ -f /etc/default/supervisor ] ; then
    . /etc/default/supervisor
fi

set -e

running_pid()
{
    # Check if a given process pid's cmdline matches a given name
    pid=\$1
    name=\$2
    [ -z "\$pid" ] && return 1
    [ ! -d /proc/\$pid ] &&  return 1
    (cat /proc/\$pid/cmdline | tr "\000" "\n"|grep -q \$name) || return 1
    return 0
}

running()
{
# Check if the process is running looking at /proc
# (works for all users)

    # No pidfile, probably no daemon present
    [ ! -f "\$PIDFILE" ] && return 1
    # Obtain the pid and check it against the binary name
    pid=\`cat \$PIDFILE\`
    running_pid \$pid \$DAEMON || return 1
    return 0
}

force_stop() {
# Forcefully kill the process
    [ ! -f "\$PIDFILE" ] && return
    if running ; then
        kill -15 \$pid
        # Is it really dead?
        [ -n "\$DODTIME" ] && sleep "\$DODTIME"s
        if running ; then
            kill -9 \$pid
            [ -n "\$DODTIME" ] && sleep "\$DODTIME"s
            if running ; then
                echo "Cannot kill \$LABEL (pid=\$pid)!"
                exit 1
            fi
        fi
    fi
    rm -f \$PIDFILE
    return 0
}

case "\$1" in
  start)
    echo -n "Starting \$DESC: "
    start-stop-daemon --start --quiet --pidfile \$PIDFILE \
        --exec \$DAEMON -- \$DAEMON_OPTS
    test -f \$PIDFILE || sleep 1
        if running ; then
            echo "\$NAME."
        else
            echo " ERROR."
        fi
    ;;
  stop)
    echo -n "Stopping \$DESC: "
    start-stop-daemon --stop --quiet --oknodo --pidfile \$PIDFILE
    echo "\$NAME."
    ;;
  force-stop)
    echo -n "Forcefully stopping \$DESC: "
        force_stop
        if ! running ; then
            echo "\$NAME."
        else
            echo " ERROR."
        fi
    ;;
  #reload)
    #
    #       If the daemon can reload its config files on the fly
    #       for example by sending it SIGHUP, do it here.
    #
    #       If the daemon responds to changes in its config file
    #       directly anyway, make this a do-nothing entry.
    #
    # echo "Reloading \$DESC configuration files."
    # start-stop-daemon --stop --signal 1 --quiet --pidfile \
    #       /var/run/\$NAME.pid --exec \$DAEMON
  #;;
  force-reload)
    #
    #       If the "reload" option is implemented, move the "force-reload"
    #       option to the "reload" entry above. If not, "force-reload" is
    #       just the same as "restart" except that it does nothing if the
    #   daemon isn't already running.
    # check wether \$DAEMON is running. If so, restart
    start-stop-daemon --stop --test --quiet --pidfile \
        /var/run/\$NAME.pid --exec \$DAEMON \
    && \$0 restart \
    || exit 0
    ;;
  restart)
    echo -n "Restarting \$DESC: "
    start-stop-daemon --stop --quiet --pidfile \
        /var/run/\$NAME.pid --exec \$DAEMON
    [ -n "\$DODTIME" ] && sleep \$DODTIME
    start-stop-daemon --start --quiet --pidfile \
        /var/run/\$NAME.pid --exec \$DAEMON -- \$DAEMON_OPTS
    echo "\$NAME."
    ;;
  status)
    echo -n "\$LABEL is "
    if running ;  then
        echo "running"
    else
        echo " not running."
        exit 1
    fi
    ;;
  *)
    N=/etc/init.d/\$NAME
    # echo "Usage: \$N {start|stop|restart|reload|force-reload}" >&2
    echo "Usage: \$N {start|stop|restart|force-reload|status|force-stop}" >&2
    exit 1
    ;;
esac

exit 0
EOF
chmod +x /etc/init.d/supervisor

for i in `seq 0 6`; do ln -s /etc/init.d/supervisor /etc/rc${i}.d/S99supervisor; done


## Configure the serial port at boot
cat << EOF > /opt/openmotics/bin/configure_serial.sh
#!/bin/bash
echo 20 > /sys/kernel/debug/omap_mux/uart1_rxd
echo 0 > /sys/kernel/debug/omap_mux/uart1_txd
EOF
chmod +x /opt/openmotics/bin/configure_serial.sh

cat << EOF > /etc/supervisor/conf.d/configure_serial.conf 
[program:configure_serial]
command=/opt/openmotics/bin/configure_serial.sh
autostart=true
autorestart=false
directory=/opt/openmotics/bin/
startsecs=0
exitcodes=0
EOF

## Install VPN service
cat << EOF > /etc/supervisor/conf.d/vpn_keepalive.conf 
[program:vpn_keepalive]
command=python /opt/openmotics/VpnService/VpnService.py
autostart=true
autorestart=true
directory=/opt/openmotics/VpnService
startsecs=10
EOF

## Install OpenVPN service
cat << EOF > /etc/supervisor/conf.d/openvpn.conf 
[program:openvpn]
command=openvpn --config vpn.conf
autostart=false
autorestart=true
directory=/opt/openmotics/etc
startsecs=10
EOF

## Install Openmotics service
cat << EOF > /etc/supervisor/conf.d/openmotics.conf 
[program:openmotics]
command=python /opt/openmotics/OpenMoticsService/Main.py
autostart=true
autorestart=true
directory=/opt/openmotics/OpenMoticsService
startsecs=10
EOF

## Install update service
cat << EOF > /etc/supervisor/conf.d/updater.conf 
[program:updater]
command=python /opt/openmotics/UpdateService/update.py
autostart=true
autorestart=true
directory=/opt/openmotics/UpdateService
startsecs=10
EOF


## Compile and install the bootloader
opkg install qt4-x11-free-dev eglibc-gconv eglibc-gconv-unicode eglibc-gconv-utf-16

cd $CUR_DIR/Bootloader/Bootload/
make
cd ../QextSerialPort
make
cd ../AN1310cl
make
cp AN1310cl /opt/openmotics/bin/
cd ..
cp devices.db /opt/openmotics/bin/
cd ..

