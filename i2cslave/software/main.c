#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

#define GPIO_INOUT_OE 0x2

int main(void)
{
    char value = 0;
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("I2C runtime built "__DATE__" "__TIME__"\n");

/*
    while(1)
    {
        gpio_inout__w_write(value | GPIO_INOUT_OE);
        value = 1 - value;
    }
*/

    while(1)
    {
        gpio_inout__w_write(clock__r_read() | GPIO_INOUT_OE);
    }

    return 0;
}
