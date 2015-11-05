#include <generated/csr.h>
#ifdef CSR_I2C_BASE
#include "i2c.h"

/* I2C bit banging */

static inline void i2c_delay(void)
{
	__asm__("nop");
	__asm__("nop");
	__asm__("nop");
}


void i2c_slave_wait_for_start_bit(void)
{
	int state = 0;
	i2c_w_write(0); // SDA as input
	do {
		switch (state)
		{
			case 0:
				if (i2c_r_read() == (I2C_SCLIN | I2C_SDAIN))
					state = 1;
				break;
			case 1:
				if (i2c_r_read() == I2C_SCLIN)
					state = 2;
				else if (i2c_r_read() != (I2C_SCLIN | I2C_SDAIN))
					state = 0;
				break;
		}
	} while (state != 2);
}

unsigned char i2c_slave_read_byte(void)
{
	unsigned char bit;
	unsigned char byte;

	for(bit = 0 ; bit < 8 ; bit++)
	{
		while(i2c_r_read() & I2C_SCLIN); // wait for falling edge
		while(! (i2c_r_read() & I2C_SCLIN)); // wait for rising edge
		byte <<= 1;
		byte |= (i2c_r_read() & I2C_SDAIN);
	}
	i2c_w_write(I2C_SDAOE); // ACK
	__asm__("nop");
	__asm__("nop");
	i2c_w_write(0); // SDA as input
	return byte;
}

unsigned char i2c_slave_read_addr(void)
{
	unsigned char byte = i2c_slave_read_byte();
	return byte >> 1;
}

#endif
