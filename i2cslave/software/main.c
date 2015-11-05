#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

#include "i2c.h"

int main(void)
{
    unsigned char addr, val;
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("I2C runtime built "__DATE__" "__TIME__"\n");

    while(1) {
        printf("waiting for start bit\n");
        i2c_slave_wait_for_start_bit();
        addr = i2c_slave_read_addr();
        val = i2c_slave_read_byte();
        printf("received addr: %02X\n", addr);
        printf("received byte: %02X\n", val);
    }
    return 0;
}
