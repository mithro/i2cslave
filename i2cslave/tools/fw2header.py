import sys
import struct


def print_bin_to_header(bin, filename):
    with open(filename, "w+") as f:
        l = len(bin)
        header = "unsigned char fx2fw[" + str(l) + "] = {"
        header += ",".join(["0x{:02X}".format(b) for b in bin])
        header += "};"

        f.write(header)


if __name__ == "__main__":
    print(sys.argv[1])
    print(sys.argv[2])
    eeprom = bytes()
    fw = bytes()
    with open(sys.argv[1], "rb") as f:
        fw += f.read()
        fw_len = len(fw)
        eeprom = b'\xC2\xaa\x55\x11\x22\x33\x44\x00'
        eeprom += struct.pack(">H", fw_len)
        eeprom += struct.pack(">H", 0)
        eeprom += fw
        eeprom += b'\x80\x01\xE6\x00\x00\x00\x00\x00'

    print_bin_to_header(eeprom, sys.argv[2])