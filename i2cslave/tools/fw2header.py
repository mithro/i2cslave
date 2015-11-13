import struct
import argparse
import sys


def getparser():
    p = argparse.ArgumentParser(description="Firmware to Header tool")
    p.add_argument("-i", "--input", required=True,
                   help="input file in .bin format.")
    p.add_argument("-o", "--output", default="firmware.h",
                   help="output header file. Default: firmware.h")
    p.add_argument("-s", "--speed", default=400, type=int, choices=[100, 400],
                   help="I2C bootload speed in kHz. Default is 100."
                        " Choices are 100 or 400")
    return p


def print_bin_to_header(eeprom, filename):
    with open(filename, "w+") as f:
        l = len(eeprom)
        header = "unsigned char fx2fw[" + str(l) + "] = {"
        header += ",".join(["0x{:02X}".format(b) for b in eeprom])
        header += "};"

        f.write(header)


if __name__ == "__main__":
    args = getparser().parse_args()
    eeprom = bytes()
    fw = bytes()

    if args.input.endswith(".ihx") or args.input.endswith(".hex"):
        print("""Error: the input file needs to be in .bin format
You can convert a .hex (or .ihex) into .bin by using objcopy.
eg: $ objcopy -Iihex -Obinary in.hex out.bin""")
        sys.exit(1)

    with open(args.input, "rb") as f:
        fw += f.read()
        fw_len = len(fw)

        if args.speed == 100:
            config_byte = b'\x00'  # 100 kHz
        else:
            config_byte = b'\x01'  # 400 kHz

        eeprom = b'\xC2\xaa\x55\x11\x22\x33\x44' + config_byte
        eeprom += struct.pack(">H", fw_len)
        eeprom += struct.pack(">H", 0)
        eeprom += fw
        eeprom += b'\x80\x01\xE6\x00\x00\x00\x00\x00'

    print_bin_to_header(eeprom, args.output)
