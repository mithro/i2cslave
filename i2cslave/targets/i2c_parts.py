#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

from migen import *
from migen.fhdl.specials import Tristate

def parse_line(x):
    l = None
    bits = []
    for i in x:
        if False:
            pass
        elif i in ("_", "▁", "/"):
            i = 0
        elif i in ("▔", "\\"):
            i = 1
        elif i in ("-",):
            i = l
        elif i in ("X",):
            i = None
        else:
            i = int(i)
        bits.append(i)
        l = i
    assert bits[0] is not None
    return bits


def parse_block(b):
    lines = [x.strip().split() for x in b.splitlines() if not x.startswith('#') and len(x) > 0]

    real = {}
    for name, signal in lines:
        real[name] = parse_line(signal)
  
    # Check all the signals are the same length
    first_key = list(real.keys())[0]
    slen = len(real[first_key])
    for name in real:
        assert slen == len(real[name])

    return slen, real


def TestHelper(in_signals, expected_signals, cut):
    in_slen, in_signals = parse_block(in_signals)
    ex_slen, ex_signals = parse_block(expected_signals)

    assert in_slen == ex_slen

    dut = cut()
    ios = set()
    for i in in_signals:
        ios.add(getattr(dut, i))
    for i in ex_signals:
        ios.add(getattr(dut, i))
    from migen.fhdl import verilog
    print("="*75)
    print(cut.__name__)
    print("-"*75)
    print(verilog.convert(dut, ios=ios))
    print("="*75)

    errors = []
    def test(d):
        for i in range(0, in_slen):
            for sig in in_signals:
                yield getattr(d, sig).eq(in_signals[sig][i])
            for sig in ex_signals:
                expected = ex_signals[sig][i]
                if expected is not None:
                    yield getattr(d, "expected_%s" % sig).eq(expected)
            # Commit the input signals
            yield
            # Wait one cycle
            yield
            # Read the results
            for sig in ex_signals:
                expected = ex_signals[sig][i]
                value = yield getattr(d, sig)
                if expected is not None and expected != value:
                    errors.append("%20s@%04i - %r != %r" % (sig, i, expected, value))
            # Pump the clock a couple of times
            yield
            yield
            yield
            yield

    dut = cut()
    for sig in ex_signals:
        exec("""
dut.expected_{0} = Signal(name="expected_{0}", reset={1})
""".format(sig, ex_signals[sig][0]))

    run_simulation(dut, test(dut), vcd_name="%s.vcd" % (cut.__name__))
    for e in errors:
        print(e)
    assert not errors, "Test on %s failed with %s errors" % (cut.__name__, len(errors))


def Shift(sig, direction, d=0):
    if direction == "right":
        return Cat(sig[1:], d)
    elif direction == "left":
        return Cat(d, sig[:-1])

def Rotate(sig, direction):
    if direction == "right":
        return Shift(sig, "right", sig[0])
    elif direction == "left":
        return Shift(sig, "left", sig[-1])



def I2CPads(Module):
    def __init__(self, pads, obj):
        self.specials += Tristate(pads.scl, obj.scl_w, obj.scl_oe, obj.self.scl_r)
        self.specials += Tristate(pads.sda, obj.sda_w, obj.sda_oe, obj.sda_r)
        

class I2CStartCondition(Module):
    """
    A start condition is SDA going low and then SCL going low.
    """
    def __init__(self):
        self.scl = Signal(reset=1)      # Clock signal
        self.sda = Signal(reset=1)      # Data signal
        self.detected = Signal(reset=0) # Detected start condition
        self.submodules.fsm = fsm = FSM("DETECT_PRE")

        # Starting from SCL and SDA high. 
        fsm.act("DETECT_PRE",   # 00
            If((self.scl == 1) & (self.sda == 1), NextState("DETECT_SDA")),
        )

        # SCL is high and SDA is high, wait for SDA to go low
        fsm.act("DETECT_SDA",   # 01
            If(self.scl != 1, NextState("DETECT_PRE")),
            If(self.sda == 0, NextState("DETECT_SCL")),
        )

        # SDA is low, wait for SCL to go low
        fsm.act("DETECT_SCL",   # 10
            If(self.sda != 0, NextState("DETECT_PRE")),
            If(self.scl == 0, NextState("DETECTED")),
        )

        # We have a start condition!
        fsm.act("DETECTED",     # 11
            self.detected.eq(1),
            NextState("DETECT_PRE"),
        )


class I2CStopCondition(Module):
    """
    Stop conditions are defined by a 0->1 (low to high) transition on SDA after
    a 0->1 transition on SCL, with SCL remaining high.
    """
    def __init__(self):
        self.scl = Signal(reset=1)      # Clock signal
        self.sda = Signal(reset=1)      # Data signal
        self.detected = Signal(reset=0) # Detected stop condition

        self.submodules.fsm = fsm = FSM("DETECT_PRE")

        # Starting from SCL and SDA low. 
        fsm.act("DETECT_PRE",   # 00
            If((self.scl == 0) & (self.sda == 0), NextState("DETECT_SCL")),
        )

        # SCL is low and SDA is low, wait for SCL to go high
        fsm.act("DETECT_SCL",   # 01
            If(self.sda != 0, NextState("DETECT_PRE")),
            If(self.scl == 1, NextState("DETECT_SDA")),
        )

        # SCL is high and SDA is low, wait for SDA to go high
        fsm.act("DETECT_SDA",   # 10
            If(self.scl != 1, NextState("DETECT_PRE")),
            If(self.sda == 1, NextState("DETECTED")),
        )

        # We have a stop condition!
        fsm.act("DETECTED",     # 11
            self.detected.eq(1),
            NextState("DETECT_PRE"),
        )


class I2CAcker(Module):
    """Module which handles the ACK in I2C (with clock stretching).

    Setting ack.eq(1) will cause module to drive SDA low for one cycle.
    Setting hold.eq(1) will cause module to drive SCL low until it is released.
    """

    def __init__(self):
        # Clock signal
        self.scl_oe = scl_oe = Signal(reset=0)
        self.scl_r = scl_r = Signal(reset=1)
        self.scl_w = scl_w = Signal(reset=0)

        # Data signal
        self.sda_oe = sda_oe = Signal(reset=0)
        self.sda_r = sda_r = Signal(reset=1)
        self.sda_w = sda_w = Signal(reset=0)

        self.run = run = Signal(reset=0)
        self.ack = ack = Signal(reset=0)
        self.hold = hold = Signal(reset=0)
        self.finished = finished = Signal(reset=0)

        self.submodules.fsm = fsm = FSM("INIT")
        fsm.act("INIT",
            If((run == 1),
                NextState("WAITING_START"),
            ),
        )

        fsm.act("WAITING_START",
            If(scl_r == 0,
                NextValue(sda_oe, ack),
                NextValue(sda_w, 0),
                NextValue(scl_oe, hold),
                NextValue(scl_w,  0),
                NextState("STRETCHING"),
            ),
        )

        fsm.act("STRETCHING",
            If(hold == 0,
                NextValue(scl_oe, 0),
                NextState("WAITING_SCL_HIGH"),
            ),
        )

        fsm.act("WAITING_SCL_HIGH",
            If(scl_r == 1,
                NextState("WAITING_SCL_LOW"),
            ),
        )

        fsm.act("WAITING_SCL_LOW",
            If(scl_r == 0,
                NextValue(sda_oe, 0),
                NextState("DONE"),
            ),
        )

        fsm.act("DONE",
            finished.eq(1),
        )

        # If we stop running, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(run == 0, NextState("INIT")))


class I2CDataShifter(Module):
    """Module which handles the shifting of 8 bits of data."""

    DATA_SIZE = 8

    def __init__(self):
        self.scl = scl = Signal(reset=1) # Clock signal
        self.sda_r = sda_r = Signal(reset=1) # Data signal
        self.sda_w = sda_w = Signal(reset=1) # Data signal

        # Signals to the outside world
        self.din = din = Signal(self.DATA_SIZE)
        self.dout = dout = Signal(self.DATA_SIZE, reset=0xA6)
        self.run = run = Signal(reset=0)
        self.finished = finished = Signal(reset=0)

        self.submodules.fsm = fsm = FSM("INIT")
        fsm.act("INIT",         # 000
            If((run == 1) & (scl == 0),
                NextState("SHIFT_OUT_0"),
            ),
        )

        for i in range(0, self.DATA_SIZE):
            shift_out = "SHIFT_OUT_{}".format(i)
            shifted_out = "SHIFTED_OUT_{}".format(i)
            shift_in = "SHIFT_IN_{}".format(i)
            shifted_in = "SHIFTED_IN_{}".format(i)

            # Data changes while SCL is low
            fsm.act(shift_out,
                NextValue(sda_w, dout[0]),
                NextValue(dout, Shift(dout, "left")),
                NextState(shifted_out),
            )

            fsm.act(shifted_out,
                If(scl == 1,
                    NextState(shift_in),
                ),
            )

            # Data should be stable while SCL is high
            fsm.act(shift_in,
                NextValue(din, Shift(din, "left", sda_r)),
                NextState(shifted_in),
            )

            fsm.act(shifted_in,
                If(scl == 0,
                    NextState([
                        "SHIFT_OUT_{}".format(i+1),
                        "DONE"
                        ][i == self.DATA_SIZE-1]
                    )
                )
            )

        fsm.act("DONE",
            finished.eq(1),
        )

        # If we stop running, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(run == 0, NextState("INIT")))


class I2CEngine(Module):
    def __init__(self):

        # Clock signal
        self.scl_w = Signal()
        self.scl_r = Signal()
        self.scl_oe = Signal()

        # Data signal
        self.sda_w = Signal()
        self.sda_r = Signal()
        self.sda_oe = Signal()

        self.comb += [
            self.scl_w.eq(0),
            self.scl_oe.eq(0),
        ]

        self.submodules.start = start = I2CStartCondition(self.scl_r, self.sda_r)
        self.submodules.stop = stop = I2CStopCondition(self.scl_r, self.sda_r)
        self.submodules.data = data = I2CDataShifter(self.scl_r, self.sda_r)
        self.submodules.ack = ack = I2CAcker(self.scl_oe, self.scl_w, self.scl_r, self.sda_r)

        self.submodules.fsm = fsm = FSM("IDLE")
        # Nothing happening
        fsm.act("IDLE",
            If(start.detected == 1,
                NextValue(self.data_current, 0),
                NextState("ADDR"),
            ),
        )

        # Reading addr byte
        fsm.act("ADDR",
            data.run.eq(1),
            If(data.finished == 1,
                NextState("ADDR_ACK"),
            ),
        )

        # Ack the addr byte
        fsm.act("ADDR_ACK",
            ack.run.eq(1),
            If(ack.finished == 1,
                NextState("DATA"),
            )
        )

        # Reading the data bytes
        fsm.act("DATA",
            data.run.eq(1),
            If(data.finished == 1,
                NextState("DATA_ACK"),
            ),
        )

        # Ack the data byte
        fsm.act("DATA_ACK",
            ack.run.eq(1),
            If(ack.finished == 1,
                NextState("WAITING"),
            )
        )

        # Wait for either,
        #  * Start of next data byte
        #  * Start condition
        #  * Stop condition
        fsm.act("WAITING",
            # Just more data
            If(self.scl_r == 0,
                NextState("DATA"),
            ),
            # Repeated start condition
            If(start.detected == 1,
                NextState("ADDR"),
            ),
            # Stop condition is added below
        )

        # If at any time we detect a stop condition, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(self.stop.detect == 1, NextState("IDLE")))


if __name__ == "__main__":
    i2c_frame =r"""
#            S   0       1       2       3       4       5       6       7       A
#   sda  XXXXXXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XX_______XXXXXXXX
    scl  ▔▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔▔
    sda  ▔▔\_____1-------0-------1-------0-------0-------0-------0-------0------------____/▔▔▔
"""

    TestHelper(
        i2c_frame,
        r"""
detected _____▔_______________________________________________________________________________
""",
        I2CStartCondition)

    TestHelper(
        i2c_frame,
        r"""
detected __________________________________________________________________________________▔__
""",
        I2CStopCondition)

    i2c_acking =r"""
   sda_r _---------------------------------_________--______________---
   scl_r ▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\__-------__/▔▔▔\___
     run ____________________▔▔▔▔▔▔▔▔____▔▔▔▔▔▔▔▔▔▔▔▔_▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔__
     ack __/▔▔▔\___/▔▔▔\_________________▔▔▔▔▔▔▔▔▔▔▔▔-▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
    hold ___/▔▔▔\___/▔▔▔\_____________________________▔▔▔▔▔▔▔__________
"""
    TestHelper(
        i2c_acking,
        r"""
finished ___________________________▔_______________▔_______________▔__
  scl_oe _____________________________________________/▔▔▔▔▔\__________
  scl_w  _XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX________XXXXXXXXXX
  sda_oe __________________________________/▔▔▔▔▔▔▔\__/▔▔▔▔▔▔▔▔▔▔▔▔\___
  sda_w  _XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX_________XX______________XXX
""",
        I2CAcker)

    i2c_frame =r"""
#            S   0       1       2       3       4       5       6       7       A
#   sda  XXXXXXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XXXX----XX_______XXXXXXXX
    scl  ▔▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔▔
  sda_r  ▔▔\_____1-------0-------1-------0-------0-------0-------0-------0------------____/▔▔▔
    run  ______▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔______________
"""
    TestHelper(
        i2c_frame,
        r"""
finished _____________________________________________________________________▔▔______________
""",
        I2CDataShifter)

