include ../include/generated/variables.mak
include $(MISOC_DIRECTORY)/software/common.mak

PYTHON ?= python3

OBJECTS=main.o isr.o i2c.o

CFLAGS += -I.

all: runtime.bin runtime.fbi

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	@chmod -x $@

%.fbi: %.bin
	@echo " MSCIMG  " $@ && $(PYTHON) -m misoc.tools.mkmscimg -f -o $@ $<

runtime.elf: $(OBJECTS) libs
	$(LD) $(LDFLAGS) \
		-T $(SOFTWARE_DIRECTORY)/linker.ld \
		-N -o $@ \
		../libbase/crt0-$(CPU).o \
		$(OBJECTS) \
		-L../libbase \
		-L../libcompiler_rt \
		-lbase-nofloat -lcompiler_rt
	@chmod -x $@

main.o: $(SOFTWARE_DIRECTORY)/main.c $(SOFTWARE_DIRECTORY)/firmware.h
	$(compile)

%.o: $(SOFTWARE_DIRECTORY)/%.c
	$(compile)

%.o: $(SOFTWARE_DIRECTORY)/%.S
	$(assemble)

libs:
	$(MAKE) -C ../libcompiler_rt
	$(MAKE) -C ../libbase

clean:
	$(RM) $(OBJECTS)
	$(RM) runtime.elf runtime.bin runtime.fbi .*~ *~

.PHONY: all clean libs
