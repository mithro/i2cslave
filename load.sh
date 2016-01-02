#! /bin/bash

set -x
set -e

python -m i2cslave.targets.pipistrello_i2c --no-compile-gateware
/usr/local/google/home/tansell/foss/timvideos/hdmi2usb/HDMI2USB-misoc-firmware/third_party/misoc/tools/flterm --port /dev/ttyUSB1 --kernel ./misoc_i2csoc_pipistrello_i2c/software/software/runtime.bin
