#!/bin/bash

## Set the system clock
echo server ntp.ubuntu.com > /etc/ntp.conf
killall ntpd
ntpd -q -g -x

## Install cherrypy
wget http://openmotics.com:8100/distro/CherryPy-3.2.2.tar.gz
wget http://openmotics.com:8100/distro/cherrypy-https.patch
tar xzf CherryPy-3.2.2.tar.gz
cd CherryPy-3.2.2
patch -p1 < ../cherrypy-https.patch
python setup.py build
python setup.py install
cd ..

## Install OpenVPN
wget http://openmotics.com:8100/distro/openvpn-2.2.2.tar.gz
tar xzf openvpn-2.2.2.tar.gz
cd openvpn-2.2.2
./configure --disable-lzo
make
make install
cd ..

## Install supervisord
wget http://openmotics.com:8100/distro/supervisor-3.0a12.tar.gz
wget http://openmotics.com:8100/distro/supervisor.init
wget http://openmotics.com:8100/distro/supervisord.conf

tar xzf supervisor-3.0a12.tar.gz
cd supervisor-3.0a12
python setup.py install
cd ..

mkdir /etc/supervisor/
mkdir /etc/supervisor/conf.d/
mkdir /var/log/supervisor/

mv supervisord.conf /etc/supervisord.conf
mv supervisor.init /etc/init.d/supervisor
chmod +x /etc/init.d/supervisor

for i in `seq 0 6`; do ln -s /etc/init.d/supervisor /etc/rc${i}.d/S99supervisor; done

## Install python sqlite3
wget http://openmotics.com:8100/distro/python-sqlite3_2.7.2-r3.17_armv7a.ipk
opkg install python-sqlite3_2.7.2-r3.17_armv7a.ipk

## Keep the log files in RAM
cat << EOF >> /etc/fstab
tmpfs                /var/log             tmpfs      defaults              0  0
EOF

## Make status display (i2c-2) accessible
mkdir /mnt/boot/
mount /dev/mmcblk0p1 /mnt/boot/
cat << EOF > /mnt/boot/uEnv.txt
optargs="run_hardware_tests i2c_bus=2,100 quiet"
EOF
umount /mnt/boot/
rm -R /mnt/boot
