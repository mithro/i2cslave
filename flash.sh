#!/bin/bash
#python -m i2cslave.targets.pipistrello_i2c

set -x
set -e

CABLE=papilio
PROXY=bscan_spi_lx45_csg324.bit
BIOS_ADDR=0x170000
RUNTIME_ADDR=0x180000
BIN_PREFIX=$PWD/binaries
PROXY_PATH=$HOME/.migen

rm -rf $BIN_PREFIX
mkdir $BIN_PREFIX
cp misoc_i2csoc_pipistrello_i2c/gateware/top.bit $BIN_PREFIX
cp misoc_i2csoc_pipistrello_i2c/software/bios/bios.bin $BIN_PREFIX
cp misoc_i2csoc_pipistrello_i2c/software/software/runtime.fbi $BIN_PREFIX
cd binaries

xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/top.bit:w:0x0:BIT
xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/bios.bin:w:$BIOS_ADDR:BIN
xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/runtime.fbi:w:$RUNTIME_ADDR:BIN
