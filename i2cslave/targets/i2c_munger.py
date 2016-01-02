#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

from migen import *
from migen.fhdl.specials import Tristate

class I2CPads(Module):
    def __init__(self, pads, obj):
        self.submodules += obj
        self.specials += Tristate(pads.scl, obj.scl_w, obj.scl_oe, obj.scl_r)
        self.specials += Tristate(pads.sda, obj.sda_w, obj.sda_oe, obj.sda_r)
        

class I2CMunger(Module):
    def __init__(self):

        # Data signal
        self.scl_w = Signal()
        self.scl_r = Signal()
        self.scl_oe = Signal()

        # Data signal
        self.sda_w = Signal()
        self.sda_r = Signal()
        self.sda_oe = Signal()

        self.current_bit = Signal(min=0, max=8)

        self.comb += [
            self.scl_w.eq(0),
            self.scl_oe.eq(0),
            self.sda_w.eq(0),
        ]

        self.submodules.fsm = fsm = FSM()
        # Start condition
        # -----
        fsm.act("DETECT_START_PRE", #0
            If(self.scl_r == 1 and self.sda_r == 1, NextState("DETECT_START_SDA")),
        )

        # SCL is high and SDA is high, wait for SDA to go low
        fsm.act("DETECT_START_SDA", #1
            If(self.scl_r != 1, NextState("DETECT_START_PRE")),
            If(self.sda_r == 0, NextState("DETECT_START_SCL")),
        )

        # SDA is low but SCL high, wait for SCL to go low
        fsm.act("DETECT_START_SCL", #2
            If(self.sda_r != 0, NextState("DETECT_START_PRE")),
            If(self.scl_r == 0, NextState("DETECTED_START")),
        )

        fsm.act("DETECTED_START", #3
            NextValue(self.current_bit, 0),
            NextState("DATA_WAIT"))
        
        # Reading data
        # Every time SCL goes high we have data.
        # Data for 8 bits.
        fsm.act("DATA_WAIT", #4
            If(self.current_bit == 2, self.sda_oe.eq(1)),
            If(self.current_bit == 3, self.sda_oe.eq(1)),
            If(self.scl_r == 1, NextState("DATA_READY")),
        )

        fsm.act("DATA_READY", #5
            If(self.current_bit == 2, self.sda_oe.eq(1)),
            If(self.scl_r == 0,
                If(self.current_bit < 7,
                    NextValue(self.current_bit, self.current_bit+1),
                    NextState("DATA_WAIT"),
                ).Else(
                    NextState("DETECT_START_PRE"),
                ),
            ),
        )


if __name__ == "__main__":
    #run_simulation(my_blinker, ncycles=200, vcd_name="i2c_munger.vcd")

    lines = [x.split() for x in """\
             S   0       1       2       3       4       5       6       7       A
sda    ▔▔\▁▁▁▁▁----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----▁▁▁▁▁▁▁▁▁/▔▔▔▔▔▔▔
sda_oe ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\▁▁▁▁▁▁▁▁/▔▔▔▔▔▔▔
sda_w  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
sda_r  ▔▔\▁▁▁▁▁1-------0-------1-------0-------0-------0-------0-------0------------/▔▔▔▔▔▔▔
scl_r  ▔▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔▔
""".splitlines()[2:]]

    lines = [x.split() for x in """\
             S   0       1       2       3       4       5       6      7
sda    ▔▔\▁▁▁▁▁----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----
sda_oe ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔\▁▁▁▁▁▁▁/▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
sda_w  ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
sda_r  ▔▔\▁▁▁▁▁1-------0-------1-------0-------0-------0-------0-------0-------/▔▔▔
scl_r  ▔▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔\▁▁▁/▔▔▔
""".splitlines()[2:]]

    real = {}
    for name, signal in lines:
        l = None
        bits = []
        for i in signal:
            if False:
                pass
            elif i in ("▁", "/"):
                i = 0
            elif i in ("▔", "\\"):
                i = 1
            elif i in ("-",):
                i = l
            else:
                i = int(i)
            bits.append(i)
            l = i
        real[name] = bits
    import pprint

    def test(dut):
        for sda_r, scl_r in zip(real['sda_r'], real['scl_r']):
            yield dut.sda_r.eq(sda_r)
            yield dut.scl_r.eq(scl_r)
            yield
            yield
            yield
            yield
            yield
            yield

    dut = I2CMunger()
    run_simulation(dut, test(dut), vcd_name="test.vcd")

