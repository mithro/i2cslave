#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

#include "i2c.h"

char fake_fw[128] = {0xaa, 0x55, 2, 12, 4, 5, 6, 7, 8};

int main(void)
{
    unsigned char addr = 0;
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("I2C runtime built "__DATE__" "__TIME__"\n");


    i2c_slave_addr_write(0x50);
    i2c_shift_reg_write(fake_fw[addr]);
    i2c_status_write(I2C_STATUS_SHIFT_REG_READY);
    while(1) {
        unsigned char status = i2c_status_read();
        if(status == I2C_STATUS_SHIFT_REG_EMPTY) // there's been a master READ
        {
            puts("READ\n");
            i2c_shift_reg_write(fake_fw[++addr]);
            i2c_status_write(I2C_STATUS_SHIFT_REG_READY);
        } else if(status == I2C_STATUS_SHIFT_REG_FULL) // there's been a master WRITE
        {
            printf("WRITE %02X\n", addr);
            addr = i2c_shift_reg_read();
            i2c_shift_reg_write(fake_fw[addr]);
            i2c_status_write(I2C_STATUS_SHIFT_REG_READY);

        } else if (status != 0)
            printf("wuut? %02X\n", status);
    }
    return 0;
}
