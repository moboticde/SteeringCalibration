# Installation Guides

## Linux-Systems

### MB3U

#### Install the FTDI D2xx driver

Download the official drivers for the FTDI D2XX series.
[Download link](https://www.ftdichip.com/Drivers/D2XX.htm)

The following installation guide uses the driver version 1.4.8 (x64). For other driver versions substitute the respective version number.

Open a console, e.g. bash, and go to the download folder.

Unpack the archive with the command:
```bash
tar xvf libftd2xx-x86_64-1.4.8.gz
```

Switch to superuser with:
```bash
sudo -s
```
Or if ``sudo`` is not available on your system
```bash
su
```

Copy the actual driver library to the library system directory.
The library system directory depends on your operating system.
Typical paths are ``/usr/local/lib``, ``/usr/local/lib64``,
``/lib``, ``/lib64``, or ``/usr/lib``.
```bash
cp release/build/libftd2xx.so.1.4.8 /usr/local/lib
```

Make the library available to users:
```bash
ldconfig
chmod 0755 /usr/local/lib/libftd2xx.so.1.4.8
```

#### Create udev-Entry

Open bash console with superuser rights. Then enter the following commands:
```bash
echo '# Unload iC-Haus FTDI devices from wrong serial driver' >> /etc/udev/rules.d/99-ftdi-ichaus.rules
echo "ATTRS{idVendor}==\"0403\", ATTRS{idProduct}==\"6010\", ATTRS{manufacturer}==\"iC-Haus\", RUN+=\"/bin/sh -c 'echo \$kernel > /sys/bus/usb/drivers/ftdi_sio/unbind'\"" >> /etc/udev/rules.d/99-ftdi-ichaus.rules
echo '# FTDI permissions granted to all users' >> /etc/udev/rules.d/99-ftdi-ichaus.rules
echo 'ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", ATTRS{manufacturer}=="iC-Haus", MODE:="0666", SYMLINK+="ichaus_ftdi"' >> /etc/udev/rules.d/99-ftdi-ichaus.rules
udevadm control --reload
```


### MB4U, and MB5U

#### Install libusb

Install libusb via your package manager.
The following command is an example for the Debian package manager ``apt``
```bash
apt install libusb-1.0-0
```

#### Create udev-Entry for MB4U

Open bash console with superuser rights. Then enter the following commands:
```bash
echo 'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="1ae4", ATTR{idProduct}=="0003", MODE="0666"' > /etc/udev/rules.d/99-mb4u-ichaus.rules
udevadm control --reload
```

#### Create udev-Entry for MB5U

Open bash console with superuser rights. Then enter the following commands:
```bash
echo 'SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="1ae4", ATTR{idProduct}=="3101", MODE="0666"' > /etc/udev/rules.d/99-mb5u-ichaus.rules
udevadm control --reload
```
