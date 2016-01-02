#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

#include "i2c.h"
#include "firmware.h"

#define I2C_SLAVE_ADDRESS 0x40

#define SET_ADDR(x) do { addr = (x) % sizeof(fx2fw); } while(false)

inline uint8_t get_eeprom_value(size_t addr) {
	uint8_t r = 0xff;
	if (addr < sizeof(mb2fw)) {
		printf("R");
		r = mb2fw.bytes[addr];
	} else {
		printf("r");
	}
        //printf("%04x %02x\n", addr, r);

	return r;
}

int main(void)
{
    size_t addr = 0x0;
    unsigned char loading_low = 0;
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("I2C runtime built "__DATE__" "__TIME__"\n");

    i2c_slave_addr_write(I2C_SLAVE_ADDRESS);
    i2c_shift_reg_write(get_eeprom_value(addr));
    i2c_status_write(I2C_STATUS_SHIFT_REG_READY);
    puts("Started!");
    while(1) {
        unsigned char status = i2c_status_read();
        if(status == I2C_STATUS_SHIFT_REG_EMPTY) // there's been a master READ
        {
            addr++;
            i2c_shift_reg_write(get_eeprom_value(addr));
            i2c_status_write(I2C_STATUS_SHIFT_REG_READY);
        } else if(status == I2C_STATUS_SHIFT_REG_FULL) // there's been a master WRITE
        {
            if(loading_low)
                addr |= i2c_shift_reg_read() & 0xFF;
            else
                addr = i2c_shift_reg_read() << 8;
            if(loading_low)
                i2c_shift_reg_write(get_eeprom_value(addr));
            loading_low = 1 - loading_low;
            i2c_status_write(I2C_STATUS_SHIFT_REG_READY);

        } else if (status != 0)
            printf("wuut? %02X\n", status);
    }
    return 0;
}
