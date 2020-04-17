# Copyright (c) 2012-2013 ARM Limited
# All rights reserved.
#
# The license below extends only to copyright in the software and shall
# not be construed as granting a license to any other intellectual
# property including but not limited to intellectual property relating
# to a hardware implementation of the functionality of the software
# licensed hereunder.  You may use the software subject to the license
# terms below provided that you ensure that this notice is replicated
# unmodified and in its entirety in all distributions of the software,
# modified or unmodified, in source code or in binary form.
#
# Copyright (c) 2015 The University of Bologna
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Authors: Erfan Azarkhish
#          Abdul Mutaal Ahmad

# A Simplified model of a complete HMC device. Based on:
#  [1] http://www.hybridmemorycube.org/specification-download/
#  [2] High performance AXI-4.0 based interconnect for extensible smart memory
#      cubes(E. Azarkhish et. al)
#  [3] Low-Power Hybrid Memory Cubes With Link Power Management and Two-Level
#      Prefetching (J. Ahn et. al)
#  [4] Memory-centric system interconnect design with Hybrid Memory Cubes
#      (G. Kim et. al)
#  [5] Near Data Processing, Are we there yet? (M. Gokhale)
#      http://www.cs.utah.edu/wondp/gokhale.pdf
#  [6] openHMC - A Configurable Open-Source Hybrid Memory Cube Controller
#      (J. Schmidt)
#  [7] Hybrid Memory Cube performance characterization on data-centric
#      workloads (M. Gokhale)
#
# This script builds a complete HMC device composed of vault controllers,
# serial links, the main internal crossbar, and an external hmc controller.
#
# - VAULT CONTROLLERS:
#   Instances of the HMC_2500_1x32 class with their functionality specified in
#   dram_ctrl.cc
#
# - THE MAIN XBAR:
#   This component is simply an instance of the NoncoherentXBar class, and its
#   parameters are tuned to [2].
#
# - SERIAL LINKS CONTROLLER:
#   SerialLink is a simple variation of the Bridge class, with the ability to
#   account for the latency of packet serialization and controller latency. We
#   assume that the serializer component at the transmitter side does not need
#   to receive the whole packet to start the serialization. But the
#   deserializer waits for the complete packet to check its integrity first.
#
#   * Bandwidth of the serial links is not modeled in the SerialLink component
#     itself.
#
#   * Latency of serial link controller is composed of SerDes latency + link
#     controller
#
#   * It is inferred from the standard [1] and the literature [3] that serial
#     links share the same address range and packets can travel over any of
#     them so a load distribution mechanism is required among them.
#
#   -----------------------------------------
#   | Host/HMC Controller                   |
#   |        ----------------------         |
#   |        |  Link Aggregator   |  opt    |
#   |        ----------------------         |
#   |        ----------------------         |
#   |        |  Serial Link + Ser | * 4     |
#   |        ----------------------         |
#   |---------------------------------------
#   -----------------------------------------
#   | Device
#   |        ----------------------         |
#   |        |       Xbar         | * 4     |
#   |        ----------------------         |
#   |        ----------------------         |
#   |        |  Vault Controller  | * 16    |
#   |        ----------------------         |
#   |        ----------------------         |
#   |        |     Memory         |         |
#   |        ----------------------         |
#   |---------------------------------------|
#
#   In this version we have present 3 different HMC archiecture along with
#   alongwith their corresponding test script.
#
#   same: It has 4 crossbars in HMC memory. All the crossbars are connected
#   to each other, providing complete memory range. This archicture also covers
#   the added latency for sending a request to non-local vault(bridge in b/t
#   crossbars). All the 4 serial links can access complete memory. So each
#   link can be connected to separate processor.
#
#   distributed: It has 4 crossbars inside the HMC. Crossbars are not
#   connected.Through each crossbar only local vaults can be accessed. But to
#   support this architecture we need a crossbar between serial links and
#   processor.
#
#   mixed: This is a hybrid architecture. It has 4 crossbars inside the HMC.
#   2 Crossbars are connected to only local vaults. From other 2 crossbar, a
#   request can be forwarded to any other vault.

from __future__ import print_function
from __future__ import absolute_import

import argparse

import m5
from m5.objects import *
from m5.util import *

def HMC_debug(desc, msg):
    print("HMC: "),
    print(desc+": "),
    print(msg)

def add_options(parser):
    # *****************************CROSSBAR PARAMETERS*************************
    # Flit size of the main interconnect [1]
    parser.add_option("--xbar-width", default=32, action="store", type="int",
                        help="Data width of the main XBar (Bytes)")
    # PIM: Keep this at 32. The DRAM is programmed to retrieve 32 bytes at a time. We wanna expose that directly to the CPU.

    # Clock frequency of the main interconnect [1]
    # This crossbar, is placed on the logic-based of the HMC and it has its
    # own voltage and clock domains, different from the DRAM dies or from the
    # host.
    parser.add_option("--xbar-frequency", default='1GHz', type="string",
                        help="Clock Frequency of the main XBar")

    # Arbitration latency of the HMC XBar [1]
    parser.add_option("--xbar-frontend-latency", default=1, action="store",
                        type="int", help="Arbitration latency of the XBar")

    # Latency to forward a packet via the interconnect [1](two levels of FIFOs
    # at the input and output of the inteconnect)
    parser.add_option("--xbar-forward-latency", default=2, action="store",
                        type="int", help="Forward latency of the XBar")

    # Latency to forward a response via the interconnect [1](two levels of
    # FIFOs at the input and output of the inteconnect)
    parser.add_option("--xbar-response-latency", default=2, action="store",
                        type="int", help="Response latency of the XBar")

    # # number of cross which connects 16 Vaults to serial link[7]
    # parser.add_option("--number-mem-crossbar", default=4, action="store",
    #                     type="int", help="Number of crossbar in HMC")
    # PIM: Automatically make the same number of crossbars = number of serial links = number of vaults = number of CPUS

    # *****************************SERIAL LINK PARAMETERS**********************
    # Number of serial links controllers [1]
    # parser.add_option("--num-links-controllers", default=4, action="store",
    #                     type="int", help="Number of serial links")
    # PIM: Automatically make the same number of crossbars = number of serial links = number of vaults = number of CPUS

    # Number of packets (not flits) to store at the request side of the serial
    #  link. This number should be adjusted to achive required bandwidth
    parser.add_option("--link-buffer-size-req", default=10, action="store",
                        type="int", help="Number of packets to buffer at the\
                        request side of the serial link")

    # Number of packets (not flits) to store at the response side of the serial
    #  link. This number should be adjusted to achive required bandwidth
    parser.add_option("--link-buffer-size-rsp", default=10, action="store",
                        type="int", help="Number of packets to buffer at the\
                        response side of the serial link")

    # Latency of the serial link composed by SER/DES latency (1.6ns [4]) plus
    # the PCB trace latency (3ns Estimated based on [5])
    # parser.add_option("--link-latency", default='4.6ns', type="string",
    #                     help="Latency of the serial links")
    # PIM: This isn't even used. It's just total control latency

    # Clock frequency of the each serial link(SerDes) [1]
    parser.add_option("--link-frequency", default='10GHz', type="string",
                        help="Clock Frequency of the serial links")

    # Clock frequency of serial link Controller[6]
    # clk_hmc[Mhz]= num_lanes_per_link * lane_speed [Gbits/s] /
    # data_path_width * 10^6
    # clk_hmc[Mhz]= 16 * 10 Gbps / 256 * 10^6 = 625 Mhz
    parser.add_option("--link-controller-frequency", default='625MHz',
                        type="string", help="Clock Frequency of the link\
                        controller")

    # Latency of the serial link controller to process the packets[1][6]
    # (ClockDomain = 625 Mhz )
    # used here for calculations only
    # parser.add_option("--link-ctrl-latency", default=4, action="store",
    #                     type="int", help="The number of cycles required for the\
    #                     controller to process the packet")
    # PIM: Not even used. Account for changes in total control latency

    # total_ctrl_latency = link_ctrl_latency + link_latency
    # total_ctrl_latency = 4(Cycles) * 1.6 ns +  4.6 ns
    parser.add_option("--total-ctrl-latency", default='11ns', type="string",
                        help="The latency experienced by every packet\
                        regardless of size of packet")
    # PIM: We may want to lower these latencies... not sure what role the "controllers" play in PIM

    # Number of parallel lanes in each serial link [1]
    parser.add_option("--num-lanes-per-link", default=16, action="store",
                        type="int", help="Number of lanes per each link")
    # PIM: Change this to 32, we wanna expose the full DRAM bandwidth to the CPUs directly

    # # Number of serial links [1]
    # parser.add_option("--num-serial-links", default=4, action="store",
    #                     type="int", help="Number of serial links")
    # PIM: Automatically make the same number of crossbars = number of serial links = number of vaults = number of CPUS

    # speed of each lane of serial link - SerDes serial interface 10 Gb/s
    parser.add_option("--serial-link-speed", default=10, action="store",
                        type="int", help="Gbs/s speed of each lane of serial\
                        link")
    # PIM: We probably wanna raise this. Find the bandwidth that DRAM is capable of and match that.

    # address range for each of the serial links
    parser.add_option("--serial-link-addr-range", default='4GB', type="string",
                        help="memory range for each of the serial links.\
                        Default: 4GB")
    # PIM: We're making everything fully connected. Change from 1GB to 4GB
    # PIM: This has to match size of vault * number of vaults

    # *****************************PERFORMANCE MONITORING*********************
    # The main monitor behind the HMC Controller
    parser.add_option("--enable-global-monitor", action="store_true",
                        help="The main monitor behind the HMC Controller")

    # The link performance monitors
    parser.add_option("--enable-link-monitor", action="store_true",
                        help="The link monitors")

    # link aggregator enable - put a cross between buffers & links
    parser.add_option("--enable-link-aggr", action="store_true", help="The\
                        crossbar between port and Link Controller")

    parser.add_option("--enable-buff-div", action="store_true",
                        help="Memory Range of Buffer is ivided between total\
                        range")

    # *****************************HMC ARCHITECTURE **************************
    # Memory chunk for 16 vault - numbers of vault / number of crossbars
    # parser.add_option("--mem-chunk", default=4, action="store", type="int",
    #                     help="Chunk of memory range for each cross bar in\
    #                     arch 0")
    # PIM: This is useless. Each crossbar just access a single vault now.

    # size of req buffer within crossbar, used for modelling extra latency
    # when the reuqest go to non-local vault
    parser.add_option("--xbar-buffer-size-req", default=10, action="store",
                        type="int", help="Number of packets to buffer at the\
                        request side of the crossbar")

    # size of response buffer within crossbar, used for modelling extra latency
    # when the response received from non-local vault
    parser.add_option("--xbar-buffer-size-resp", default=10, action="store",
                        type="int", help="Number of packets to buffer at the\
                        response side of the crossbar")
    # HMC device architecture. It affects the HMC host controller as well
    # parser.add_option("--arch", type="choice", choices=["same", "distributed",
    #                     "mixed"], default="distributed", help="same: HMC with\
    #                     4 links, all with same range.\ndistributed: HMC with\
    #                     4 links with distributed range.\nmixed: mixed with\
    #                     same and distributed range.\nDefault: distributed")
    # PIM: We're going rogue and making our own. We can consider putting these back in later if we want

    # HMC device - number of vaults
    parser.add_option("--hmc-dev-num-vaults", default=16, action="store",
                        type="int", help="number of independent vaults within\
                        the HMC device. Note: each vault has a memory\
                        controller (valut controller)\nDefault: 16")
    # HMC device - vault capacity or size
    parser.add_option("--hmc-dev-vault-size", default='256MB', type="string",
                        help="vault storage capacity in bytes. Default:\
                        256MB")
    # parser.add_option("--mem-type", type="choice", choices=["HMC_2500_1x32"],
    #                     default="HMC_2500_1x32", help="type of HMC memory to\
    #                     use. Default: HMC_2500_1x32")
    # # PIM: Keep the underlying DRAM instance the same

    # parser.add_option("--mem-channels", default=1, action="store", type="int",
    #                     help="Number of memory channels")
    # parser.add_option("--mem-ranks", default=1, action="store", type="int",
    #                     help="Number of ranks to iterate across")
    # # PIM: These should always stay at one. They are the parameters for a single vault of DRAM.

    parser.add_option("--burst-length", default=256, action="store",
                        type="int", help="burst length in bytes. Note: the\
                        cache line size will be set to this value.\nDefault:\
                        256")
    # PIM: May want to play with this depending on the size of data we're accessing. Especially if we bypass caches. (If possible, DRAM row buffer is also 256 bytes). 


# configure HMC host controller
def config_hmc_host_ctrl(opt, system):

    # create HMC host controller
    system.hmc_host = SubSystem()

    clk = '100GHz'
    vd = VoltageDomain(voltage='1V')

    # PIM: Make a mem xbar for each serial link to connect to the outside world
    # PIM: Make all external connections directly to system.memx[i].slave
    num_memx = opt.hmc_dev_num_vaults
    system.memx = [NoncoherentXBar(width=opt.xbar_width,
                                    frontend_latency=3,
                                    forward_latency=4,
                                    response_latency=2) for i in range(num_memx)]

    # PIM: Finish out memx config
    cd = SrcClockDomain(clock=clk, voltage_domain=vd)
    for i in range(num_memx):
        system.memx[i].badaddr_responder = BadAddr()
        system.memx[i].default = Self.badaddr_responder.pio
        system.memx[i].clk_domain = cd

    # create memory ranges for the serial links
    slar = convert.toMemorySize(opt.serial_link_addr_range)
    HMC_debug("Serial Link Address Range", slar)

    # Memmory ranges of serial link for arch-0. Same as the ranges of vault
    # controllers (4 vaults to 1 serial link)
    # if opt.arch == "same":
    #     ser_ranges = [AddrRange(0, (4*slar)-1) for i in
    #                   range(opt.num_serial_links)]
    # # Memmory ranges of serial link for arch-1. Distributed range accross
    # # links
    # if opt.arch == "distributed":
    #     ser_ranges = [AddrRange(i*slar, ((i+1)*slar)-1) for i in
    #                   range(opt.num_serial_links)]
    # # Memmory ranges of serial link for arch-2 'Mixed' address distribution
    # # over links
    # # 2 can access everything, 2 can access only local. Only the local links are connected to the mem bus. The other two shouldn't even get serial links...?
    # if opt.arch == "mixed":
    #     ser_range0 = AddrRange(0, (1*slar)-1)
    #     ser_range1 = AddrRange(1*slar, 2*slar-1)
    #     ser_range2 = AddrRange(0, (4*slar)-1)
    #     ser_range3 = AddrRange(0, (4*slar)-1)
    #     ser_ranges = [ser_range0, ser_range1, ser_range2, ser_range3]

    # Serial link Controller with 16 SerDes links at 10 Gbps with serial link
    # ranges w.r.t to architecture 
    # PIM: Give all serial links full access to the whole memory.
    num_serial_links = opt.hmc_dev_num_vaults
    sl = [SerialLink(ranges=slar,
                     req_size=opt.link_buffer_size_req,
                     resp_size=opt.link_buffer_size_rsp,
                     num_lanes=opt.num_lanes_per_link,
                     link_speed=opt.serial_link_speed,
                     delay=opt.total_ctrl_latency) for i in range(num_serial_links)]
    system.hmc_host.seriallink = sl

    # enable global monitor
    if opt.enable_global_monitor:
        system.hmc_host.lmonitor = [CommMonitor() for i in
                                    range(num_serial_links)]

    # set the clock frequency for serial link
    for i in range(num_serial_links):
        clk = opt.link_controller_frequency
        vd = VoltageDomain(voltage='1V')
        scd = SrcClockDomain(clock=clk, voltage_domain=vd)
        system.hmc_host.seriallink[i].clk_domain = scd

    # PIM: Connect all links to a memx to the outside world
    hh = system.hmc_host
    for i in range(num_serial_links):
        if opt.enable_global_monitor:
            system.memx[i].master = hh.lmonitor[i].slave
            hh.lmonitor[i].master = hh.seriallink[i].slave
        else:
            system.memx[i].master = hh.seriallink[i].slave

    # if opt.arch == "distributed":
    #     mb = system.membus
    #     for i in range(opt.num_links_controllers):
    #         if opt.enable_global_monitor:
    #             mb.master = hh.lmonitor[i].slave
    #             hh.lmonitor[i].master = hh.seriallink[i].slave
    #         else:
    #             mb.master = hh.seriallink[i].slave
    # if opt.arch == "mixed":
    #     mb = system.membus
    #     if opt.enable_global_monitor:
    #         mb.master = hh.lmonitor[0].slave
    #         hh.lmonitor[0].master = hh.seriallink[0].slave
    #         mb.master = hh.lmonitor[1].slave
    #         hh.lmonitor[1].master = hh.seriallink[1].slave
    #     else:
    #         mb.master = hh.seriallink[0].slave # This is a problem. Not all seial links are getting assigned. The two that access everything are never connected.
    #         mb.master = hh.seriallink[1].slave

    # if opt.arch == "same":
    #     mb = system.membus
    #     for i in range(opt.num_links_controllers): # four serial links, all connected to all 4 GB of memory.
    #         if opt.enable_global_monitor:
    #             mb.master = hh.lmonitor[i].slave
    #             hh.lmonitor[i].master = hh.seriallink[i].slave
    #         else:
    #             mb.master = hh.seriallink[i].slave

    return system


# Create an HMC device
def config_hmc_dev(opt, system):
    print("Creating HMC Device")
    
    # create HMC device
    system.hmc_dev = SubSystem()

    # PIM: Dictate everything from the number of vaults
    number_mem_crossbar = opt.hmc_dev_num_vaults
    num_links_controllers = opt.hmc_dev_num_vaults

    # create memory ranges for the vault controllers
    arv = convert.toMemorySize(opt.hmc_dev_vault_size) # 256 MB per vault
    addr_ranges_vaults = [AddrRange(start=i*arv, size=arv) for i in
                          range(opt.hmc_dev_num_vaults)]
    system.mem_ranges = addr_ranges_vaults # This gets past to mem_config to make more controllers -> this is a controller per vault

    # if opt.enable_link_monitor:
    #     lm = [CommMonitor() for i in range(num_links_controllers)]
    #     system.hmc_dev.lmonitor = lm

    # HMC Crossbars located in its logic-base (LoB)
    xb = [NoncoherentXBar(width=opt.xbar_width, # Keep this 32, that's the same as the DRAM bandwidth per vault
                          frontend_latency=opt.xbar_frontend_latency,
                          forward_latency=opt.xbar_forward_latency,
                          response_latency=opt.xbar_response_latency) for i in
          range(number_mem_crossbar)]
    system.hmc_dev.xbar = xb

    for i in range(number_mem_crossbar):
        clk = opt.xbar_frequency
        vd = VoltageDomain(voltage='1V')
        scd = SrcClockDomain(clock=clk, voltage_domain=vd)
        system.hmc_dev.xbar[i].clk_domain = scd

    # Attach a serial link to each crossbar/s
    # for i in range(number_mem_crossbar):
    #     if opt.enable_link_monitor:
    #         system.hmc_host.seriallink[i].master = system.hmc_dev.lmonitor[i].slave
    #         system.hmc_dev.lmonitor[i].master = system.hmc_dev.xbar[i].slave
    #     else:
    #         system.hmc_host.seriallink[i].master = system.hmc_dev.xbar[i].slave

    # PIM: Connect All Crossbars together to give all CPUs full access to memory (Copied below from "same")
    numx = len(system.hmc_dev.xbar)
    
    # create a list of buffers
    system.hmc_dev.buffers = [Bridge(req_size=opt.xbar_buffer_size_req,
                                resp_size=opt.xbar_buffer_size_resp)
                                for i in range(numx*(numx-1))] 
    
    # Buffer iterator
    it = iter(range(len(system.hmc_dev.buffers)))

    # iterate over all the crossbars and connect them as required
    for i in range(numx): # for each crossbar
        for j in range(numx): # connect it to every other crossbar
            # connect xbar to all other xbars except itself
            if i != j:
                # get the next index of buffer
                index = it.next()

                # Change the default values for ranges of bridge
                system.hmc_dev.buffers[index].ranges = system.mem_ranges[j] # This bridge now has access to the memory jth crossbar = jth vault

                # Connect the bridge between corssbars ... all crossbars can now drive all other crossbars
                system.hmc_dev.xbar[i].master = system.hmc_dev.buffers[index].slave
                system.hmc_dev.buffers[index].master = system.hmc_dev.xbar[j].slave                
            else:
                # Don't connect the xbar to itself
                pass





    # Connecting xbar with each other for request arriving at the wrong xbar,
    # then it will be forward to correct xbar. Bridge is used to connect xbars
    # if opt.arch == "same":
    #     numx = len(system.hmc_dev.xbar)

    #     # create a list of buffers
    #     system.hmc_dev.buffers = [Bridge(req_size=opt.xbar_buffer_size_req,
    #                                      resp_size=opt.xbar_buffer_size_resp)
    #                               for i in range(numx*(numx-1))] # number of crossbars = 4 * number of other crossbars = 4 - 1 (don't connect to yurself) -> 12 bridges. One from every crossbar to every ther crossbar. (are these only one way bridges??)

    #     # Buffer iterator
    #     it = iter(range(len(system.hmc_dev.buffers)))

    #     # necesarry to add system_port to one of the xbar
    #     # system.system_port = system.hmc_dev.xbar[3].slave

    #     # iterate over all the crossbars and connect them as required
    #     for i in range(numx): # for each crossbar
    #         for j in range(numx): # connect it to every other crossbar
    #             # connect xbar to all other xbars except itself
    #             if i != j:
    #                 # get the next index of buffer
    #                 index = it.next()

    #                 # Change the default values for ranges of bridge
    #                 system.hmc_dev.buffers[index].ranges = system.mem_ranges[ # There are 16 mem ranges for 16 vaults ... there are only 4 crossbars
    #                         j * int(opt.mem_chunk): # each cross bar gets access to mem_chunk number of vaults ... but this isn't really an independent variable :P
    #                         (j + 1) * int(opt.mem_chunk)] # The range that this bridge can now access is the range of the jth crossbar

    #                 # Connect the bridge between corssbars (I think you can have multiple slaves feeding one master and vice versa, so this is ok.)
    #                 system.hmc_dev.xbar[i].master = system.hmc_dev.buffers[index].slave
    #                 system.hmc_dev.buffers[index].master = system.hmc_dev.xbar[j].slave
    #             else:
    #                 # Don't connect the xbar to itself
    #                 pass

    # Two crossbars are connected to all other crossbars-Other 2 vault
    # can only direct traffic to it local vaults
    # if opt.arch == "mixed":
    #     system.hmc_dev.buffer30 = Bridge(ranges=system.mem_ranges[0:4])
    #     system.hmc_dev.xbar[3].master = system.hmc_dev.buffer30.slave
    #     system.hmc_dev.buffer30.master = system.hmc_dev.xbar[0].slave

    #     system.hmc_dev.buffer31 = Bridge(ranges=system.mem_ranges[4:8])
    #     system.hmc_dev.xbar[3].master = system.hmc_dev.buffer31.slave
    #     system.hmc_dev.buffer31.master = system.hmc_dev.xbar[1].slave

    #     system.hmc_dev.buffer32 = Bridge(ranges=system.mem_ranges[8:12])
    #     system.hmc_dev.xbar[3].master = system.hmc_dev.buffer32.slave
    #     system.hmc_dev.buffer32.master = system.hmc_dev.xbar[2].slave

    #     system.hmc_dev.buffer20 = Bridge(ranges=system.mem_ranges[0:4])
    #     system.hmc_dev.xbar[2].master = system.hmc_dev.buffer20.slave
    #     system.hmc_dev.buffer20.master = system.hmc_dev.xbar[0].slave

    #     system.hmc_dev.buffer21 = Bridge(ranges=system.mem_ranges[4:8])
    #     system.hmc_dev.xbar[2].master = system.hmc_dev.buffer21.slave
    #     system.hmc_dev.buffer21.master = system.hmc_dev.xbar[1].slave

    #     system.hmc_dev.buffer23 = Bridge(ranges=system.mem_ranges[12:16])
    #     system.hmc_dev.xbar[2].master = system.hmc_dev.buffer23.slave
    #     system.hmc_dev.buffer23.master = system.hmc_dev.xbar[3].slave
