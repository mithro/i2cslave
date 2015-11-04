# i2cslave
i2cslave done in bitbanging by LM32 softcore CPU

#### Dependencies

* [Migen](https://github.com/m-labs/migen)
* [MiSoC](https://github.com/m-labs/misoc)
* [Xilinx ISE toolchain](http://www.xilinx.com/support/download/index.html/content/xilinx/en/downloadNav/design-tools.html)
* lm32-elf gcc/binutils toolchain
* Python 3.4

#### Building

```bash
$ python setup.py develop --user
$ python -m i2cslave.targets.pipistrello_i2c
```

#### Flashing

You need to install the flash proxy in `$HOME/.migen`: 
```bash
$ mkdir -p $HOME/.migen
$ cd $HOME/.migen
$ wget https://people.phys.ethz.ch/~robertjo/bscan_spi_lx45_csg324.bit
```

You also need to install xc3sprog: 
```bash
$ mkdir -p $HOME/dev
$ cd $HOME/dev
$ svn co http://svn.code.sf.net/p/xc3sprog/code/trunk xc3sprog
$ cd xc3sprog
$ cmake . && make
$ sudo make install
```

Gather binaries to flash:

```bash
mkdir -p binaries
cp misoc_i2csoc_pipistrello_i2c/gateware/top.bit binaries/
cp misoc_i2csoc_pipistrello_i2c/software/bios/bios.bin binaries/
cp misoc_i2csoc_pipistrello_i2c/software/software/runtime.fbi binaries/
cd binaries
```

Then you can flash:

```bash
$ CABLE=papilio
$ PROXY=bscan_spi_lx45_csg324.bit
$ BIOS_ADDR=0x170000
$ RUNTIME_ADDR=0x180000
$ BIN_PREFIX=$PWD
$ PROXY_PATH=$HOME/.migen

$ xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/top.bit:w:0x0:BIT
$ xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/bios.bin:w:$BIOS_ADDR:BIN
$ xc3sprog -v -c $CABLE -I$PROXY_PATH/$PROXY $BIN_PREFIX/runtime.fbi:w:$RUNTIME_ADDR:BIN

```
