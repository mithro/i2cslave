#ifndef __I2C_H
#define __I2C_H

#define I2C_SDAOE	0x01
#define I2C_SDAOUT	0x02

#define I2C_SDAIN	0x01
#define I2C_SCLIN   0x02

unsigned char i2c_slave_read_addr(void);
unsigned char i2c_slave_read_byte(void);
void i2c_slave_wait_for_start_bit(void);
unsigned char i2c_slave_read_byte_asm(void);

#endif /* __I2C_H */
