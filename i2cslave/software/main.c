#include <stdio.h>
#include <string.h>
#include <irq.h>
#include <uart.h>
#include <console.h>
#include <system.h>
#include <generated/csr.h>
#include <hw/flags.h>

int main(void)
{
    irq_setmask(0);
    irq_setie(1);
    uart_init();

    puts("I2C runtime built "__DATE__" "__TIME__"\n");

    return 0;
}
