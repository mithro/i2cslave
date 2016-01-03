#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

from migen import *
from migen.fhdl.specials import Tristate

def I2CPads(Module):
    def __init__(self, pads, obj):
        self.specials += Tristate(pads.scl, obj.scl_w, obj.scl_oe, obj.self.scl_r)
        self.specials += Tristate(pads.sda, obj.sda_w, obj.sda_oe, obj.sda_r)
        

class I2CStartCondition(Module):
    """
    A start condition is SDA going low and then SCL going low.
    """
    def __init__(self, scl, sda):
        self.scl = Signal() # Clock signal
        self.sda = Signal() # Data signal
        self.comb = [
            self.scl.eq(scl),
            self.sda.eq(sda),
        ]
        self.detected = Signal(0)
        self.submodules.fsm = fsm = FSM("START_DETECT_PRE")

        # Starting from SCL and SDA high. 
        fsm.act("START_DETECT_PRE",
            If(self.scl == 1 and self.sda == 1, NextState("START_DETECT_SDA")),
        )

        # SCL is high and SDA is high, wait for SDA to go low
        fsm.act("START_DETECT_SDA",
            If(self.scl != 1, NextState("START_DETECT_PRE")),
            If(self.sda == 0, NextState("START_DETECT_SCL")),
        )

        # SDA is low, wait for SCL to go low
        fsm.act("START_DETECT_SCL",
            If(self.sda != 0, NextState("START_DETECT_PRE")),
            If(self.scl == 0, NextState("START_DETECTED")),
        )

        # We have a start condition!
        fsm.act("START_DETECTED",
            self.detected.eq(1),
            NextState("START_DETECT_PRE"),
        )


class I2CStopCondition(Module):
    """
    Stop conditions are defined by a 0->1 (low to high) transition on SDA after
    a 0->1 transition on SCL, with SCL remaining high.
    """
    def __init__(self, scl, sda):
        self.scl = Signal() # Clock signal
        self.sda = Signal() # Data signal
        self.comb = [
            self.scl.eq(scl),
            self.sda.eq(sda),
        ]
        self.detected = Signal(0)
        self.submodules.fsm = fsm = FSM("STOP_DETECT_PRE")

        # Starting from SCL and SDA low. 
        fsm.act("STOP_DETECT_PRE",
            If(self.scl == 0 and self.sda == 0, NextState("STOP_DETECT_SCL")),
        )

        # SCL is low and SDA is low, wait for SCL to go high
        fsm.act("STOP_DETECT_SCL",
            If(self.sda != 1, NextState("STOP_DETECT_PRE")),
            If(self.scl == 0, NextState("STOP_DETECT_SDA")),
        )

        # SCL is high and SDA is low, wait for SDA to go high
        fsm.act("STOP_DETECT_SDA",
            If(self.scl != 1, NextState("STOP_DETECT_PRE")),
            If(self.sda == 1, NextState("STOP_DETECTED")),
        )

        # We have a stop condition!
        fsm.act("STOP_DETECTED",
            self.detected_stopcond.eq(1),
            NextState("STOP_DETECT_PRE"),
        )


class I2CDataShifter(Module):
    DATA_SIZE = 8

    def __init__(self, scl, sda):
        self.scl = Signal() # Clock signal
        self.sda = Signal() # Data signal
        self.comb = [
            self.scl.eq(scl),
            self.sda.eq(sda),
        ]

        # Signals to the outside world
        self.din = Signal(self.DATA_SIZE)
        self.run = Signal(0)
        self.finished = Signal(0)

        self.dbits = Signal(min=0, max=self.DATA_SIZE)

        self.submodules.fsm = fsm = FSM("INIT")
        fsm.act("INIT",
            If(self.run == 1 and self.scl == 0,
                NextValue(self.dbits, 0),
                NextState("CHANGING"),
            ),
        )

        # Data changes while SCL is low
        fsm.act("CHANGING",
            If(self.scl == 1,
                NextState("STABLE")),
        )

        # Data should be stable while SCL is high
        fsm.act("STABLE",
            NextValue(self.din[self.dbits], self.sda_r),
            If(self.scl_r == 0,
                If(self.dbits < DATA_SIZE,
                    NextValue(self.dbits, self.dbits+1),
                    NextState("CHANGING"),
                ).Else(
                    NextState("DONE"),
                )
            )
        )

        fsm.act("DONE",
            self.finished.eq(1),
        )

        # If we stop running, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(self.run == 0, NextState("IDLE")))


class I2CAcker(Module):

    def __init__(self, scl_oe, scl_r, scl_w, sda):
        # Clock signal
        self.scl_oe = Signal()
        self.scl_r = Signal()
        self.scl_w = Signal()

        self.sda = Signal() # Data signal
        self.comb = [
            self.scl_oe.eq(scl_oe),
            self.scl_r.eq(scl_r),
            self.scl_w.eq(scl_w),
            self.sda.eq(sda),
        ]

        self.run = Signal()
        self.capture_ack = Signal()
        self.release_ack = Signal()

        self.submodules.fsm = fsm = FSM("INIT")
        fsm.act("INIT",
            If(self.run == 1,
                NextState("WAITING_START"),
            ),
        )

        fsm.act("WAITING_START",
            If(scl_r == 0,
                NextValue(sda_oe, self.capture_ack),
                NextValue(sda_w, 0),
                NextValue(scl_oe, ~self.release_ack),
                NextValue(scl_w,  0),
                NextState("STRETCHING"),
            ),
        )

        fsm.act("STRETCHING",
            If(self.release_ack == 1,
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
            self.finished.eq(1),
        )

        # If we stop running, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(self.run == 0, NextState("IDLE")))


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
            )
            # Stop condition is added to 
        )

        # If at any time we detect a stop condition, force everything back to IDLE
        for state in fsm.actions.keys():
            fsm.act(state, If(self.stop.detect == 1, NextState("IDLE")))





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

