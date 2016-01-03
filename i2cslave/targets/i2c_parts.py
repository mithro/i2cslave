#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

from migen import *
from migen.fhdl.specials import Tristate

from fsm_test_helpers import *

##########################################################################
##########################################################################

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

def waggle(dut, sig, check):
    yield from check(dut)
    for i in range(0, 10):
        for j in range(i, 10):
            yield from check(dut)
            yield
        yield from check(dut)
        yield sig.eq(0)
        yield from check(dut)
        yield
        yield from check(dut)
        for j in range(0, i):
            yield from check(dut)
            yield
        yield from check(dut)
        yield sig.eq(1)
        yield from check(dut)
        yield
        yield from check(dut)

##########################################################################
##########################################################################

def I2CPads(Module):
    def __init__(self, pads, obj):
        self.specials += Tristate(pads.scl, obj.scl_w, obj.scl_oe, obj.self.scl_r)
        self.specials += Tristate(pads.sda, obj.sda_w, obj.sda_oe, obj.sda_r)
        
##########################################################################
##########################################################################

class I2CStartCondition(Module):
    """
    A start condition is SDA going low and then SCL going low.
    """
    def __init__(self):
        self.scl = Signal(reset=1)      # Clock signal
        self.sda = Signal(reset=1)      # Data signal
        self.detected = Signal(reset=0) # Detected start condition
        self.submodules.fsm = fsm = FSM("PRE")

        # Starting from SCL and SDA high. 
        fsm.act("PRE",   # 00
            If((self.scl == 1) & (self.sda == 1), NextState("SDA")),
        )

        # SCL is high and SDA is high, wait for SDA to go low
        fsm.act("SDA",   # 01
            If(self.sda == 0, NextState("SCL")),
            # Take preference when both change at the same time.
            If(self.scl != 1, NextState("PRE")), 
        )

        # SDA is low, wait for SCL to go low
        fsm.act("SCL",   # 10
            If(self.scl == 0, NextState("DET")),
            # Take preference when both change at the same time.
            If(self.sda != 0, NextState("PRE")),
        )

        # We have a start condition!
        fsm.act("DET",     # 11
            self.detected.eq(1),
            NextState("PRE"),
        )

# ------------------------------------------------------------------------

def TestI2CStartCondition():
    dut = I2CStartCondition()
    state_string(dut.fsm)

    def set_initial(dut):
        yield dut.scl.eq(1)
        yield dut.sda.eq(1)
        yield
        try:
            check_state(dut.fsm, "PRE")
            yield
        except CheckFailure:
            pass
        yield from assert_state(dut.fsm, "SDA")

    def assert_not_detected(dut):
        assert (yield dut.detected) != 1

    def test(dut):

        # While SDA is high, waggle SCL
        yield from set_initial(dut)
        yield from waggle(dut, dut.scl, assert_not_detected)

        # While SCL is high, waggle SDA
        yield from set_initial(dut)
        yield from waggle(dut, dut.sda, assert_not_detected)

        # While SCL is low, waggle SDA
        yield from set_initial(dut)
        yield dut.scl.eq(0)
        yield
        yield from assert_not_detected(dut)
        yield from waggle(dut, dut.sda, assert_not_detected)
        yield
        yield dut.scl.eq(1)
        yield from assert_not_detected(dut)
        yield

        # Take SDA low, then SCL low, should cause start condition
        yield from set_initial(dut)
        yield from assert_state(dut.fsm, "SDA")
        yield dut.sda.eq(0)
        yield
        yield
        yield from assert_state(dut.fsm, "SCL")
        yield dut.scl.eq(0)
        yield
        yield
        assert (yield dut.detected) == 1

        # Both falling at the same time shouldn't cause a start condition.
        yield from set_initial(dut)
        yield dut.scl.eq(0)
        yield dut.sda.eq(0)
        yield
        assert (yield dut.fsm.next_state) == 0

    run_simulation(dut, test(dut), vcd_name="TestI2CStartCondition.vcd")

##########################################################################
##########################################################################

class I2CStopCondition(Module):
    """
    Stop conditions are defined by a 0->1 (low to high) transition on SDA after
    a 0->1 transition on SCL, with SCL remaining high.
    """
    def __init__(self):
        self.scl = Signal(reset=1)      # Clock signal
        self.sda = Signal(reset=1)      # Data signal
        self.detected = Signal(reset=0) # Detected stop condition

        self.submodules.fsm = fsm = FSM("PRE")

        # Starting from SCL and SDA low. 
        fsm.act("PRE",   # 00
            If((self.scl == 0) & (self.sda == 0), NextState("SCL")),
        )

        # SCL is low and SDA is low, wait for SCL to go high
        fsm.act("SCL",   # 01
            If(self.scl == 1, NextState("SDA")),
            # Take preference when both change at the same time.
            If(self.sda != 0, NextState("PRE")),
        )

        # SCL is high and SDA is low, wait for SDA to go high
        fsm.act("SDA",   # 10
            If(self.sda == 1, NextState("DET")),
            # Take preference when both change at the same time.
            If(self.scl != 1, NextState("PRE")),
        )

        # We have a stop condition!
        fsm.act("DET",     # 11
            self.detected.eq(1),
            NextState("PRE"),
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

##########################################################################
##########################################################################

class I2CDataShifter(Module):
    """Module which handles the shifting of 8 bits of data."""

    DATA_SIZE = 8

    def __init__(self):
        self.scl = scl = Signal(reset=1) # Clock signal
        self.sda_r = sda_r = Signal(reset=1) # Data signal
        self.sda_w = sda_w = Signal(reset=0) # Data signal

        # Signals to the outside world
        self.din = din = Signal(self.DATA_SIZE)
        self.dout = dout = Signal(self.DATA_SIZE, reset=0xA6)
        self.run = run = Signal(reset=0)
        self.finished = finished = Signal(reset=0)

        self._bit_index = bit_index = Signal(min=0, max=self.DATA_SIZE)
        self.submodules.fsm = fsm = FSM("INIT")
        fsm.act("INIT",
            If((run == 1) & (scl == 0),
                NextValue(bit_index, 0),
                NextState("SHIFT_OUT"),
            ),
        )

        # Data changes while SCL is low
        fsm.act("SHIFT_OUT",
            NextValue(sda_w, dout[0]),
            NextValue(dout, Shift(dout, "left")),
            NextState("SHIFTED_OUT"),
        )

        fsm.act("SHIFTED_OUT",
            If(scl == 1,
                NextState("SHIFT_IN"),
            ),
        )

        # Data should be stable while SCL is high
        fsm.act("SHIFT_IN",
            NextValue(din, Shift(din, "left", sda_r)),
            NextState("SHIFTED_IN"),
        )

        fsm.act("SHIFTED_IN",
            If(scl == 0,
                If(bit_index < self.DATA_SIZE-1,
                    NextValue(bit_index, bit_index+1),
                    NextState("SHIFT_OUT"),
                ).Else(
                    NextState("DONE"),
                ),
            ),
        )

        fsm.act("DONE",
            finished.eq(1),
        )

        # If we stop running, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(run == 0, NextState("INIT")))

##########################################################################
##########################################################################

class I2CStateMachine(Module):
    def __init__(self):
        self.start_detected = start_detected = Signal(reset=0)
        self.stop_detected = stop_detected = Signal(reset=0)

        self.data_run = data_run = Signal(reset=0)
        self.data_next = data_next = Signal(reset=0)
        self.data_finished = data_finished = Signal(reset=0)

        self.ack_run = ack_run = Signal(reset=0)
        self.ack_finished = ack_finished = Signal(reset=0)

        self.addr_ready = addr_ready = Signal(reset=0)
        self.data_ready = data_ready = Signal(reset=0)
        self.idle = idle = Signal(reset=0)
        self.error = error = Signal(reset=0)

        self.submodules.fsm = fsm = FSM("IDLE")

        # Reading addr byte
        fsm.act("ADDR",
            data_run.eq(1),
            If(data_finished == 1,
                NextState("ADDR_ACK"),
            ),
        )

        # Ack the addr byte
        fsm.act("ADDR_ACK",
            ack_run.eq(1),
            addr_ready.eq(1),
            If(ack_finished == 1,
                NextState("DATA"),
            )
        )

        # Reading the data bytes
        fsm.act("DATA",
            data_run.eq(1),
            If(data_finished == 1,
                NextState("DATA_ACK"),
            ),
        )

        # Ack the data byte
        fsm.act("DATA_ACK",
            ack_run.eq(1),
            data_ready.eq(1),
            If(ack_finished == 1,
                NextState("WAITING"),
            )
        )

        # If at any time we detect a stop or start condition, goto the error state
        for state in fsm.actions.keys():
            fsm.act(state, 
                If((stop_detected == 1) | (stop_detected == 1),
                    NextState("ERROR"),
                ),
            )

        # Nothing happening
        fsm.act("IDLE",
            idle.eq(1),
            If(start_detected == 1,
                NextState("ADDR"),
            ),
        )

        # Wait for either,
        #  * Start of next data byte
        #  * Start condition
        #  * Stop condition
        fsm.act("WAITING",
            data_run.eq(1),
            # Just another data byte
            If(data_next,
                NextState("DATA"),
            ),
            # Repeated start condition
            If(start_detected,
                NextState("ADDR"),
            ),
            # Stop detected
            If(stop_detected,
                NextState("IDLE"),
            ),
        )

        fsm.act("ERROR",
            error.eq(1),
        )

##########################################################################
##########################################################################

class I2CEngine(Module):
    def __init__(self):

        self.dummy = Signal(reset=0)

        # Clock signal
        self.scl_r  = scl_r  = Signal(reset=1, name="scl_r")
        self.scl_w  = scl_w  = Signal(reset=0, name="scl_w")
        self.scl_oe = scl_oe = Signal(reset=0, name="scl_oe")

        # Data signal
        self.sda_r  = sda_r  = Signal(reset=1, name="sda_r")
        self.sda_w  = sda_w  = Signal(reset=0, name="sda_w")
        self.sda_oe = sda_oe = Signal(reset=0, name="sda_oe")

        self.submodules.start = start = I2CStartCondition()
        self.comb += [start.scl.eq(scl_r), start.sda.eq(sda_r)]

        self.submodules.stop = stop = I2CStopCondition()
        self.comb += [stop.scl.eq(scl_r), stop.sda.eq(sda_r)]

        self.submodules.data = data = I2CDataShifter()
        self.comb += [
            data.scl.eq(scl_r),
            data.sda_r.eq(sda_r),
            # data.sda_w
        ]

        self.submodules.ack = ack = I2CAcker()
        self.comb += [
            ack.scl_r.eq(scl_r),
            # ack.scl_w
            # ack.scl_oe
            ack.sda_r.eq(sda_r),
            # ack.sda_w
            # ack.sda_oe
        ]

        self.submodules.state = state = I2CStateMachine()
        self.comb += [
            state.start_detected.eq(start.detected),
            state.stop_detected.eq(stop.detected),

            state.data_next.eq(data.run & (data._bit_index == 1)),
            state.data_finished.eq(data.finished),
            state.ack_finished.eq(ack.finished),

            data.run.eq(state.data_run),
            ack.run.eq(state.ack_run),
        ]

        self.address = address = Signal(7, reset=0x50)
        self.direction = direction = Signal(reset=0)

        self.comb += [
            scl_w.eq(ack.scl_w),
            scl_oe.eq(ack.scl_oe),
            sda_w.eq(data.sda_w | ack.sda_w),
            sda_oe.eq(ack.sda_oe | self.direction),
        ]

        self.sync += [
            If(state.addr_ready & (self.data.din[1:] == self.address),
                ack.ack.eq(1),
                ack.hold.eq(0),
                direction.eq(self.data.din[0]),
            ),
            If(state.idle,
                ack.ack.eq(0),
                ack.hold.eq(0),
            ),
        ]


##########################################################################
##### Testing helpers
##########################################################################

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
                    yield getattr(d, "%s_expected" % sig).eq(expected)
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
dut.{0}_expected = Signal(name="{0}_expected", reset={1})
""".format(sig, ex_signals[sig][0]))

    run_simulation(dut, test(dut), vcd_name="%s.vcd" % (cut.__name__))
    for e in errors:
        print(e)
    assert not errors, "Test on %s failed with %s errors" % (cut.__name__, len(errors))



if __name__ == "__main__":
    TestI2CStartCondition()

    i2c_frame = r"""
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

    i2c_acking = r"""
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
  scl_w  _XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX_______XXXXXXXXXX
  sda_oe __________________________________/▔▔▔▔▔▔▔\__/▔▔▔▔▔▔▔▔▔▔▔▔\___
  sda_w  _XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX_________XX______________XXX
""",
        I2CAcker)

    i2c_frame = r"""
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

    i2c_state = r"""
start_detected _▔______________▔______________
 stop_detected _____________________________▔_
 data_finished ____▔_____▔________▔_____▔_____
  ack_finished _______▔_____▔________▔_____▔__
"""

    TestHelper(
        i2c_state,
        r"""
          idle ▔____________________________▔▔
         error _______________________________
      data_run _▔▔▔___▔▔▔___▔▔▔▔▔▔___▔▔▔___▔__
       ack_run ____▔▔▔___▔▔▔______▔▔▔___▔▔▔___

    addr_ready ____▔▔▔____________▔▔▔_________
    data_ready __________▔▔▔____________▔▔▔___
""",
        I2CStateMachine)

    i2c_frame = r"""
#            S   A6      A5      A4      A3      A2      A1      A0      R/W     AA          D7      D6      D5      D4      D3      D2      D1      D0      AD        D7      D6      D5      D4      D3      D2      D1      D0      AD        P
  sda_r  ▔▔\_____1-------0-------1-------0-------0-------0-------0-------0----________/▔\___0-------1-------0-------1-------0-------1-------0-------1----________/▔\___1-------0-------1-------0-------1-------0-------1-------0----________/▔\__/▔▔▔
  scl_r  ▔▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\______/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\______/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\___/▔▔▔\____/▔▔▔▔
"""
    TestHelper(
        i2c_frame,
        r"""
 sda_oe  _____________________________________________________________________/▔▔▔▔▔▔\___________________________________________________________________/▔▔▔▔▔▔\___________________________________________________________________/▔▔▔▔▔▔\_________
  sda_w  ____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________
 scl_oe  ____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________
  scl_w  ____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________
""",
        I2CEngine)
