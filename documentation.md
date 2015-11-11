# Documentation #

## Max GPIO toggling frequency ##

This test tries to toggle as fast as possible some GPIO pin on the Pipistrello FPGA board by the mean of software bit banging on the LM32 CPU
running @ 83.3 MHz.

The gateware code used is there: 
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/targets/pipistrello_i2c.py#L48
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/targets/pipistrello_i2c.py#L201

The bit banging software code is there:
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/software/main.c#L22 from line 22 to 26

It looks like:
```C
while(1)
{
    gpio_inout__w_write(value | GPIO_INOUT_OE);
    value = 1 - value;
}
```

Here is the result as showed by my logic analyzer:
![GPIO bit banging by the LM32](screenshots/gpio_out_clock_bitbang.png)
