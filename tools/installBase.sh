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

## Install Qt packages
PACKAGES="libz1_1.2.6-r1_armv7a.ipk libc6_2.12-r28_armv7a.ipk libgcc1_4.5-r49+svnr184907_armv7a.ipk libglib-2.0-0_2.30.3-r2_armv7a.ipk libffi5_3.0.10-r0_armv7a.ipk libstdc++6_4.5-r49+svnr184907_armv7a.ipk libqtcore4_4.8.0-r48.1_armv7a.ipk libqtsql4_4.8.0-r48.1_armv7a.ipk qt4-plugin-sqldriver-sqlite_4.8.0-r48.1_armv7a.ipk"
for i in $PACKAGES; do wget http://openmotics.com:8100/distro/packages/${i}; done
opkg install $PACKAGES

## Configure filesystems
mkdir /opt

cat << EOF > /etc/fstab
rootfs               /                    auto       defaults,noatime,ro   1  1
proc                 /proc                proc       defaults              0  0
devpts               /dev/pts             devpts     mode=0620,gid=5       0  0
tmpfs                /tmp                 tmpfs      defaults              0  0
tmpfs                /var                 tmpfs      defaults              0  0
/dev/mmcblk0p3       /opt                 auto       defaults,noatime      1  1
EOF

## Make status display (i2c-2) accessible
mkdir /mnt/boot/
mount /dev/mmcblk0p1 /mnt/boot/
cat << EOF > /mnt/boot/uEnv.txt
optargs="run_hardware_tests i2c_bus=2,100 quiet"
EOF
umount /mnt/boot/
rm -R /mnt/boot

## Remove unused kernel modules
rm /etc/modules-load.d/hidp.conf
rm /etc/modules-load.d/ircomm-tty.conf
rm /etc/modules-load.d/rfcomm.conf
/usr/sbin/update-modules

## Make the beagle bone automatically restart on kernel panic
echo "kernel.panic = 10" >> /etc/sysctl.conf

## Instal Google public DNS name servers
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf



