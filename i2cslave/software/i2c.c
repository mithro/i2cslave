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

unsigned char i2c_slave_read_byte_asm(void)
{
	unsigned char byte = 0;
	asm volatile(
	"mvhi r6, 0xe000\n\t"
	"ori r6,r6,0x8800\n\t"
	"mvi r5, 1\n\t"
	"mvhi r3,0xe000\n\t"
	"ori r3,r3,0x8804\n\t"
	"mvi r2,8\n\t"
	"1: lw r4,(r3+0)\n\t"
	"andi r4,r4,0x2\n\t"
	"bne r4,r0,1b\n\t"
	"2: lw r4,(r3+0)\n\t"
	"andi r4,r4,0x2\n\t"
	"be r4,r0,2b\n\t"
	"sli %0,%0,1\n\t"
	"sub r2,r2,r5\n\t"
	"lw r4,(r3+0)\n\t"
	"andi r4,r4,0x1\n\t"
	"or %0,%0,r4\n\t"
	"bne r2,r0,1b\n\t"
	"sw (r6+0),r5\n\t"
	"nop\n\t"
	"sw (r2+0),r0\n\t" : "=r"(byte) :: "r1", "r2", "r3", "r4", "r5", "r6");
	return byte;
}

unsigned char i2c_slave_read_addr(void)
{
	unsigned char byte = i2c_slave_read_byte();
	return byte >> 1;
}

#endif
