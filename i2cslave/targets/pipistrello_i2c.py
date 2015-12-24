#!/usr/bin/env python3
# vim: set ts=4 sw=4 et sts=4 ai:

import argparse
import os
from fractions import Fraction

from migen import *
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.misc import chooser
from migen.build.generic_platform import Pins, IOStandard

from misoc.interconnect.csr import *
from misoc.integration.builder import *
from misoc.cores.sdram_settings import MT46H32M16
from misoc.cores.sdram_phy import S6HalfRateDDRPHY
from misoc.cores import spi_flash
from misoc.integration.soc_sdram import *

from ..platforms import pipistrello_i2c
from migen.build.platforms import pipistrello

i2cslave_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)))

class I2CShiftReg(Module, AutoCSR):
    def __init__(self, pads, debug_ios):

        STATUS_FULL = 1
        STATUS_EMPTY = 2

        self.shift_reg = shift_reg = CSRStorage(8, write_from_dev=True)
        self.status = status = CSRStorage(2, reset=STATUS_EMPTY, write_from_dev=True)
        self.slave_addr = slave_addr = CSRStorage(7)
        self.pads = pads

        ###

        scl_raw = Signal()
        sda_i = Signal()
        sda_raw = Signal()
        sda_drv = Signal()
        scl_drv = Signal()
        _sda_drv_reg = Signal()
        self._sda_i_async = _sda_i_async = Signal()
        self._scl_i_async = _scl_i_async = Signal()
        _scl_drv_reg = Signal()
        self.sync += _sda_drv_reg.eq(sda_drv)
        self.sync += _scl_drv_reg.eq(scl_drv)
        self.specials += [
            Tristate(pads.sda, 0, _sda_drv_reg, _sda_i_async),
            Tristate(pads.scl, 0, _scl_drv_reg, _scl_i_async),
            MultiReg(_scl_i_async, scl_raw),
            MultiReg(_sda_i_async, sda_raw),
        ]

        # for debug
        self.scl = scl_raw
        self.sda_i = sda_i
        self.sda_o = Signal()
        self.comb += self.sda_o.eq(~_sda_drv_reg)
        self.sda_oe = _sda_drv_reg

        shift_reg_full = Signal()
        shift_reg_empty = Signal()
        scl_i = Signal()
        samp_count = Signal(3)
        samp_carry = Signal()
        self.sync += [
            Cat(samp_count, samp_carry).eq(samp_count + 1),
            If(samp_carry,
                scl_i.eq(scl_raw),
                sda_i.eq(sda_raw)
            )
        ]

        scl_r = Signal()
        sda_r = Signal()
        scl_rising = Signal()
        scl_falling = Signal()
        sda_rising = Signal()
        sda_falling = Signal()
        self.sync += [
            scl_r.eq(scl_i),
            sda_r.eq(sda_i)
        ]
        self.comb += [
            debug_ios[11].eq(status.storage[0]),
            debug_ios[12].eq(status.storage[1]),
            shift_reg_full.eq(status.storage[0]),
            shift_reg_empty.eq(status.storage[1]),
            scl_rising.eq(scl_i & ~scl_r),
            scl_falling.eq(~scl_i & scl_r),
            sda_rising.eq(sda_i & ~sda_r),
            sda_falling.eq(~sda_i & sda_r)
        ]

        start = Signal()
        self.comb += start.eq(scl_i & sda_falling)

        din = Signal(8)
        counter = Signal(max=9)
        counter_reset = Signal()
        self.sync += [
            If(start | counter_reset, counter.eq(0)),
            If(scl_rising,
                If(counter == 8,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter + 1),
                    din.eq(Cat(sda_i, din[:7]))
                )
            )
        ]

        self.din = din
        self.counter = counter

        is_read = Signal()
        update_is_read = Signal()
        self.sync += If(update_is_read, is_read.eq(din[0]))
        data_bit = Signal()

        zero_drv = Signal()
        data_drv = Signal()
        pause_drv = Signal()
        self.comb += scl_drv.eq(pause_drv)
        self.comb += If(zero_drv, sda_drv.eq(1)).Elif(data_drv,
                                                      sda_drv.eq(~data_bit))

        data_drv_en = Signal()
        data_drv_stop = Signal()
        self.sync += If(data_drv_en, data_drv.eq(1)).Elif(data_drv_stop,
                                                          data_drv.eq(0))
        self.sync += If(data_drv_en, chooser(shift_reg.storage,
                                             counter, data_bit, 8,
                                             reverse=True))
        self.submodules.fsm = fsm = FSM()

        fsm.act("WAIT_START")
        fsm.act("RCV_ADDRESS",
            debug_ios[0].eq(1),
            If(counter == 8,
                If(din[1:] == slave_addr.storage,
                    update_is_read.eq(1),
                    NextState("ACK_ADDRESS0"),
                ).Else(
                    NextState("WAIT_START"),
                )
            )
        )
        fsm.act("ACK_ADDRESS0",
            debug_ios[1].eq(1),
            counter_reset.eq(1),
            If(~scl_i, NextState("ACK_ADDRESS1")),
        )
        fsm.act("ACK_ADDRESS1",
            debug_ios[2].eq(1),
            counter_reset.eq(1),
            zero_drv.eq(1),
            If(scl_i, NextState("ACK_ADDRESS2")),
        )
        fsm.act("ACK_ADDRESS2",
            debug_ios[3].eq(1),
            counter_reset.eq(1),
            zero_drv.eq(1),
            If(~scl_i,
                    NextState("PAUSE")
            )
        )
        fsm.act("PAUSE",
            debug_ios[4].eq(1),
            counter_reset.eq(1),
            pause_drv.eq(1),
            If(~shift_reg_empty & is_read,
               counter_reset.eq(1),
               NextState("DO_READ"),
            ).Elif(~shift_reg_full & ~is_read,
               NextState("DO_WRITE"),
            )
        )
        fsm.act("DO_READ",
            debug_ios[5].eq(1),
            If(~scl_i,
                If(counter == 8,
                   data_drv_stop.eq(1),
                   status.we.eq(1),
                   status.dat_w.eq(STATUS_EMPTY),
                   NextState("ACK_READ0"),
                ).Else(
                    data_drv_en.eq(1),
                )
            )
        )
        fsm.act("ACK_READ0",
            debug_ios[6].eq(1),
            counter_reset.eq(1),
            If(scl_rising,
               If(sda_i,
                  NextState("WAIT_START"),
               ).Else(
                  NextState("ACK_READ1"),
               )
            )
        )
        fsm.act("ACK_READ1",
            counter_reset.eq(1),
            If(scl_falling,
               NextState("PAUSE"),
            )
        )
        fsm.act("DO_WRITE",
            debug_ios[7].eq(1),
            If(counter == 8,
                shift_reg.dat_w.eq(din),
                shift_reg.we.eq(1),
                NextState("ACK_WRITE0"),
            )
        )
        fsm.act("ACK_WRITE0",
            debug_ios[8].eq(1),
            counter_reset.eq(1),
            If(~scl_i, NextState("ACK_WRITE1")),
        )
        fsm.act("ACK_WRITE1",
            debug_ios[9].eq(1),
            counter_reset.eq(1),
            zero_drv.eq(1),
            If(scl_i, NextState("ACK_WRITE2")),
        )
        fsm.act("ACK_WRITE2",
            debug_ios[10].eq(1),
            counter_reset.eq(1),
            zero_drv.eq(1),
            If(~scl_i,
                NextState("PAUSE"),
                status.we.eq(1),
                status.dat_w.eq(STATUS_FULL),
            )
        )

        for state in fsm.actions.keys():
            fsm.act(state, If(start, NextState("RCV_ADDRESS")))


class _CRG(Module):
    def __init__(self, platform, clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sdram_half = ClockDomain()
        self.clock_domains.cd_sdram_full_wr = ClockDomain()
        self.clock_domains.cd_sdram_full_rd = ClockDomain()

        self.clk4x_wr_strb = Signal()
        self.clk4x_rd_strb = Signal()

        f0 = Fraction(50, 1)*1000000
        p = 12
        f = Fraction(clk_freq*p, f0)
        n, d = f.numerator, f.denominator
        assert 19e6 <= f0/d <= 500e6  # pfd
        assert 400e6 <= f0*n/d <= 1080e6  # vco

        clk50 = platform.request("clk50")
        clk50a = Signal()
        self.specials += Instance("IBUFG", i_I=clk50, o_O=clk50a)
        clk50b = Signal()
        self.specials += Instance("BUFIO2", p_DIVIDE=1,
                                  p_DIVIDE_BYPASS="TRUE", p_I_INVERT="FALSE",
                                  i_I=clk50a, o_DIVCLK=clk50b)
        pll_lckd = Signal()
        pll_fb = Signal()
        pll = Signal(6)
        self.specials.pll = Instance("PLL_ADV", p_SIM_DEVICE="SPARTAN6",
                                     p_BANDWIDTH="OPTIMIZED", p_COMPENSATION="INTERNAL",
                                     p_REF_JITTER=.01, p_CLK_FEEDBACK="CLKFBOUT",
                                     i_DADDR=0, i_DCLK=0, i_DEN=0, i_DI=0, i_DWE=0, i_RST=0, i_REL=0,
                                     p_DIVCLK_DIVIDE=d, p_CLKFBOUT_MULT=n, p_CLKFBOUT_PHASE=0.,
                                     i_CLKIN1=clk50b, i_CLKIN2=0, i_CLKINSEL=1,
                                     p_CLKIN1_PERIOD=1e9/f0, p_CLKIN2_PERIOD=0.,
                                     i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb, o_LOCKED=pll_lckd,
                                     o_CLKOUT0=pll[0], p_CLKOUT0_DUTY_CYCLE=.5,
                                     o_CLKOUT1=pll[1], p_CLKOUT1_DUTY_CYCLE=.5,
                                     o_CLKOUT2=pll[2], p_CLKOUT2_DUTY_CYCLE=.5,
                                     o_CLKOUT3=pll[3], p_CLKOUT3_DUTY_CYCLE=.5,
                                     o_CLKOUT4=pll[4], p_CLKOUT4_DUTY_CYCLE=.5,
                                     o_CLKOUT5=pll[5], p_CLKOUT5_DUTY_CYCLE=.5,
                                     p_CLKOUT0_PHASE=0., p_CLKOUT0_DIVIDE=p//4,  # sdram wr rd
                                     p_CLKOUT1_PHASE=0., p_CLKOUT1_DIVIDE=p//4,
                                     p_CLKOUT2_PHASE=270., p_CLKOUT2_DIVIDE=p//2,  # sdram dqs adr ctrl
                                     p_CLKOUT3_PHASE=250., p_CLKOUT3_DIVIDE=p//2,  # off-chip ddr
                                     p_CLKOUT4_PHASE=0., p_CLKOUT4_DIVIDE=p//1,
                                     p_CLKOUT5_PHASE=0., p_CLKOUT5_DIVIDE=p//1,  # sys
        )
        self.specials += Instance("BUFG", i_I=pll[5], o_O=self.cd_sys.clk)
        reset = platform.request("user_btn")
        self.clock_domains.cd_por = ClockDomain()
        por = Signal(max=1 << 11, reset=(1 << 11) - 1)
        self.sync.por += If(por != 0, por.eq(por - 1))
        self.comb += self.cd_por.clk.eq(self.cd_sys.clk)
        self.specials += AsyncResetSynchronizer(self.cd_por, reset)
        self.specials += AsyncResetSynchronizer(self.cd_sys, ~pll_lckd | (por > 0))
        self.specials += Instance("BUFG", i_I=pll[2], o_O=self.cd_sdram_half.clk)
        self.specials += Instance("BUFPLL", p_DIVIDE=4,
                                  i_PLLIN=pll[0], i_GCLK=self.cd_sys.clk,
                                  i_LOCKED=pll_lckd, o_IOCLK=self.cd_sdram_full_wr.clk,
                                  o_SERDESSTROBE=self.clk4x_wr_strb)
        self.comb += [
            self.cd_sdram_full_rd.clk.eq(self.cd_sdram_full_wr.clk),
            self.clk4x_rd_strb.eq(self.clk4x_wr_strb),
        ]
        clk_sdram_half_shifted = Signal()
        self.specials += Instance("BUFG", i_I=pll[3], o_O=clk_sdram_half_shifted)
        clk = platform.request("ddram_clock")
        self.specials += Instance("ODDR2", p_DDR_ALIGNMENT="NONE",
                                  p_INIT=0, p_SRTYPE="SYNC",
                                  i_D0=1, i_D1=0, i_S=0, i_R=0, i_CE=1,
                                  i_C0=clk_sdram_half_shifted, i_C1=~clk_sdram_half_shifted,
                                  o_Q=clk.p)
        self.specials += Instance("ODDR2", p_DDR_ALIGNMENT="NONE",
                                  p_INIT=0, p_SRTYPE="SYNC",
                                  i_D0=0, i_D1=1, i_S=0, i_R=0, i_CE=1,
                                  i_C0=clk_sdram_half_shifted, i_C1=~clk_sdram_half_shifted,
                                  o_Q=clk.n)


class BaseSoC(SoCSDRAM):
    csr_map = {
        "spiflash": 16,
    }
    csr_map.update(SoCSDRAM.csr_map)

    def __init__(self, clk_freq=(83 + Fraction(1, 3))*1000*1000,
                 platform=pipistrello.Platform(), **kwargs):
        SoCSDRAM.__init__(self, platform, clk_freq,
                          cpu_reset_address=0x170000,  # 1.5 MB
                          **kwargs)

        self.submodules.crg = _CRG(platform, clk_freq)

        if not self.integrated_main_ram_size:
            sdram_module = MT46H32M16(self.clk_freq)
            self.submodules.ddrphy = S6HalfRateDDRPHY(platform.request("ddram"),
                                                      sdram_module.memtype,
                                                      rd_bitslip=1,
                                                      wr_bitslip=3,
                                                      dqs_ddr_alignment="C1")
            self.comb += [
                self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
                self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb),
            ]
            self.register_sdram(self.ddrphy, "minicon",
                                sdram_module.geom_settings, sdram_module.timing_settings)

        if not self.integrated_rom_size:
            self.submodules.spiflash = spi_flash.SpiFlash(platform.request("spiflash4x"),
                                                          dummy=10, div=4)

            self.config["SPIFLASH_PAGE_SIZE"] = 256
            self.config["SPIFLASH_SECTOR_SIZE"] = 0x10000
            self.flash_boot_address = 0x180000
            self.register_rom(self.spiflash.bus, 0x1000000)


papilio_adapter_io = [
    ("debug_ios", 0, Pins("C:0 C:1 C:2 C:3 C:4 C:5 C:6 C:7 C:8 C:9 C:10 C:11 C:12"), IOStandard("LVTTL")),
]


class I2CSoC(BaseSoC):

    csr_map = {
        "i2c": 17,
    }
    csr_map.update(BaseSoC.csr_map)

    def __init__(self, **kwargs):
        BaseSoC.__init__(self, platform=pipistrello_i2c.Platform(), **kwargs)

        platform = self.platform
        platform.add_extension(papilio_adapter_io)
        debug_ios = platform.request("debug_ios")
        self.submodules.i2c = I2CShiftReg(platform.request("i2c"), debug_ios)


soc_pipistrello_args = soc_sdram_args
soc_pipistrello_argdict = soc_sdram_argdict


def main():
    parser = argparse.ArgumentParser(description="MiSoC port to the Pipistrello with I2C pins")
    builder_args(parser)
    soc_pipistrello_args(parser)
    args = parser.parse_args()

    soc = I2CSoC(**soc_pipistrello_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.add_software_package("software", os.path.join(i2cslave_dir,
                                                         "..", "software"))
    builder.build()


if __name__ == "__main__":
    main()
