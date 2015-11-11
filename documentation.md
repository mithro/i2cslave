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

The bit banging code can generate a ~ 7 MHz clock while doing nothing else.

## Clock replicating ##

This tests shows the capacity of bit banging software to read a pin status and then write to another one in a tight loop.

The gateware is generating a 100 kHz clock: 
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/targets/pipistrello_i2c.py#L27
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/targets/pipistrello_i2c.py#L202

The software will, in a tight loop, sample this signal and write its value to the gpio_out pin:
* https://github.com/fallen/i2cslave/blob/bitbangtesting/i2cslave/software/main.c#L29

```C
while(1)
{
    gpio_inout__w_write(clock__r_read() | GPIO_INOUT_OE);
}
```

Let's see what happens:
![100 kHz clock replicating](https://github.com/fallen/i2cslave/blob/bitbangtesting/screenshots/clock_replication_bitbang_frequency.png)

The clock is replicated correctly, the frequency is approximately the same.

Something also interesting to have a look at is the latency of such code: the time between sampling the clock and writing to the `gpio_out` pin:
![100 kHz clock replicating : latency](https://github.com/fallen/i2cslave/blob/bitbangtesting/screenshots/clock_replication_bitbang_latency.png)

We can see that the latency is ~ 325 ns which is ~ 27 CPU clock cycles.
