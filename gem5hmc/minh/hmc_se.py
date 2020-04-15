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
# Copyright (c) 2006-2008 The Regents of The University of Michigan
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
# Authors: Steve Reinhardt

# Simple test script
#
# "m5 test.py"

from __future__ import print_function
from __future__ import absolute_import

import optparse
import sys
import os

import m5
from m5.defines import buildEnv
from m5.objects import *
from m5.util import addToPath, fatal, warn

addToPath('../')

from ruby import Ruby

from common import Options
from common import Simulation
from common import CacheConfig
from common import CpuConfig
from common import ObjectList
from common import MemConfig
from common.FileSystemConfig import config_filesystem
from common.Caches import *
from common.cpu2000 import *

def add_HMC_options(parser):
    # *****************************CROSSBAR PARAMETERS*************************
    # Flit size of the main interconnect [1]
    parser.add_option("--xbar-width", default=32, action="store", type=int,
                        help="Data width of the main XBar (Bytes)")

    # Clock frequency of the main interconnect [1]
    # This crossbar, is placed on the logic-based of the HMC and it has its
    # own voltage and clock domains, different from the DRAM dies or from the
    # host.
    parser.add_option("--xbar-frequency", default='1GHz', type=str,
                        help="Clock Frequency of the main XBar")

    # Arbitration latency of the HMC XBar [1]
    parser.add_option("--xbar-frontend-latency", default=1, action="store",
                        type=int, help="Arbitration latency of the XBar")

    # Latency to forward a packet via the interconnect [1](two levels of FIFOs
    # at the input and output of the inteconnect)
    parser.add_option("--xbar-forward-latency", default=2, action="store",
                        type=int, help="Forward latency of the XBar")

    # Latency to forward a response via the interconnect [1](two levels of
    # FIFOs at the input and output of the inteconnect)
    parser.add_option("--xbar-response-latency", default=2, action="store",
                        type=int, help="Response latency of the XBar")

    # number of cross which connects 16 Vaults to serial link[7]
    parser.add_option("--number-mem-crossbar", default=4, action="store",
                        type=int, help="Number of crossbar in HMC")

    # *****************************SERIAL LINK PARAMETERS**********************
    # Number of serial links controllers [1]
    parser.add_option("--num-links-controllers", default=4, action="store",
                        type=int, help="Number of serial links")

    # Number of packets (not flits) to store at the request side of the serial
    #  link. This number should be adjusted to achive required bandwidth
    parser.add_option("--link-buffer-size-req", default=10, action="store",
                        type=int, help="Number of packets to buffer at the\
                        request side of the serial link")

    # Number of packets (not flits) to store at the response side of the serial
    #  link. This number should be adjusted to achive required bandwidth
    parser.add_option("--link-buffer-size-rsp", default=10, action="store",
                        type=int, help="Number of packets to buffer at the\
                        response side of the serial link")

    # Latency of the serial link composed by SER/DES latency (1.6ns [4]) plus
    # the PCB trace latency (3ns Estimated based on [5])
    parser.add_option("--link-latency", default='4.6ns', type=str,
                        help="Latency of the serial links")

    # Clock frequency of the each serial link(SerDes) [1]
    parser.add_option("--link-frequency", default='10GHz', type=str,
                        help="Clock Frequency of the serial links")

    # Clock frequency of serial link Controller[6]
    # clk_hmc[Mhz]= num_lanes_per_link * lane_speed [Gbits/s] /
    # data_path_width * 10^6
    # clk_hmc[Mhz]= 16 * 10 Gbps / 256 * 10^6 = 625 Mhz
    parser.add_option("--link-controller-frequency", default='625MHz',
                        type=str, help="Clock Frequency of the link\
                        controller")

    # Latency of the serial link controller to process the packets[1][6]
    # (ClockDomain = 625 Mhz )
    # used here for calculations only
    parser.add_option("--link-ctrl-latency", default=4, action="store",
                        type=int, help="The number of cycles required for the\
                        controller to process the packet")

    # total_ctrl_latency = link_ctrl_latency + link_latency
    # total_ctrl_latency = 4(Cycles) * 1.6 ns +  4.6 ns
    parser.add_option("--total-ctrl-latency", default='11ns', type=str,
                        help="The latency experienced by every packet\
                        regardless of size of packet")

    # Number of parallel lanes in each serial link [1]
    parser.add_option("--num-lanes-per-link", default=16, action="store",
                        type=int, help="Number of lanes per each link")

    # Number of serial links [1]
    parser.add_option("--num-serial-links", default=4, action="store",
                        type=int, help="Number of serial links")

    # speed of each lane of serial link - SerDes serial interface 10 Gb/s
    parser.add_option("--serial-link-speed", default=10, action="store",
                        type=int, help="Gbs/s speed of each lane of serial\
                        link")

    # address range for each of the serial links
    parser.add_option("--serial-link-addr-range", default='1GB', type=str,
                        help="memory range for each of the serial links.\
                        Default: 1GB")

    # *****************************PERFORMANCE MONITORING*********************
    # The main monitor behind the HMC Controller
    parser.add_option("--enable-global-monitor", action="store_false",
                        help="The main monitor behind the HMC Controller")

    # The link performance monitors
    parser.add_option("--enable-link-monitor", action="store_false",
                        help="The link monitors")

    # link aggregator enable - put a cross between buffers & links
    parser.add_option("--enable-link-aggr", action="store_true", help="The\
                        crossbar between port and Link Controller")

    parser.add_option("--enable-buff-div", action="store_true",
                        help="Memory Range of Buffer is ivided between total\
                        range")

    # *****************************HMC ARCHITECTURE **************************
    # Memory chunk for 16 vault - numbers of vault / number of crossbars
    parser.add_option("--mem-chunk", default=4, action="store", type=int,
                        help="Chunk of memory range for each cross bar in\
                        arch 0")

    # size of req buffer within crossbar, used for modelling extra latency
    # when the reuqest go to non-local vault
    parser.add_option("--xbar-buffer-size-req", default=10, action="store",
                        type=int, help="Number of packets to buffer at the\
                        request side of the crossbar")

    # size of response buffer within crossbar, used for modelling extra latency
    # when the response received from non-local vault
    parser.add_option("--xbar-buffer-size-resp", default=10, action="store",
                        type=int, help="Number of packets to buffer at the\
                        response side of the crossbar")
    # HMC device architecture. It affects the HMC host controller as well
    parser.add_option("--arch", type="choice", choices=["same", "distributed",
                        "mixed"], default="distributed", help="same: HMC with\
                        4 links, all with same range.\ndistributed: HMC with\
                        4 links with distributed range.\nmixed: mixed with\
                        same and distributed range.\nDefault: distributed")
    # HMC device - number of vaults
    parser.add_option("--hmc-dev-num-vaults", default=16, action="store",
                        type=int, help="number of independent vaults within\
                        the HMC device. Note: each vault has a memory\
                        controller (valut controller)\nDefault: 16")
    # HMC device - vault capacity or size
    parser.add_option("--hmc-dev-vault-size", default='256MB', type=str,
                        help="vault storage capacity in bytes. Default:\
                        256MB")
    parser.add_option("--burst-length", default=256, action="store",
                        type=int, help="burst length in bytes. Note: the\
                        cache line size will be set to this value.\nDefault:\
                        256")

    # Options related to traffic generation
    parser.add_option("--num-tgen", default=4, action="store", type=int,
                        help="number of traffic generators.\
                        Right now this script supports only 4.\nDefault: 4")
    parser.add_option("--tgen-cfg-file",
                        default="./configs/example/hmc_tgen.cfg",
                        type=str, help="Traffic generator(s) configuration\
                        file. Note: this script uses the same configuration\
                        file for all traffic generators")

def get_processes(options):
    """Interprets provided options and returns a list of processes"""

    multiprocesses = []
    inputs = []
    outputs = []
    errouts = []
    pargs = []

    workloads = options.cmd.split(';')
    if options.input != "":
        inputs = options.input.split(';')
    if options.output != "":
        outputs = options.output.split(';')
    if options.errout != "":
        errouts = options.errout.split(';')
    if options.options != "":
        pargs = options.options.split(';')

    idx = 0
    for wrkld in workloads:
        process = Process(pid = 100 + idx)
        process.executable = wrkld
        process.cwd = os.getcwd()

        if options.env:
            with open(options.env, 'r') as f:
                process.env = [line.rstrip() for line in f]

        if len(pargs) > idx:
            process.cmd = [wrkld] + pargs[idx].split()
        else:
            process.cmd = [wrkld]

        if len(inputs) > idx:
            process.input = inputs[idx]
        if len(outputs) > idx:
            process.output = outputs[idx]
        if len(errouts) > idx:
            process.errout = errouts[idx]

        multiprocesses.append(process)
        idx += 1

    if options.smt:
        assert(options.cpu_type == "DerivO3CPU")
        return multiprocesses, idx
    else:
        return multiprocesses, 1

######################### CFG Begin  ###########################################
parser = optparse.OptionParser()
Options.addCommonOptions(parser)
Options.addSEOptions(parser)
add_HMC_options(parser)

if '--ruby' in sys.argv:
    Ruby.define_options(parser)

(options, args) = parser.parse_args()

if args:
    print("Error: script doesn't take any positional arguments")
    sys.exit(1)

multiprocesses = []
numThreads = 1

######################### Making workloads  ####################################
if options.bench:
    apps = options.bench.split("-")
    if len(apps) != options.num_cpus:
        print("number of benchmarks not equal to set num_cpus!")
        sys.exit(1)

    for app in apps:
        try:
            if buildEnv['TARGET_ISA'] == 'alpha':
                exec("workload = %s('alpha', 'tru64', '%s')" % (
                        app, options.spec_input))
            elif buildEnv['TARGET_ISA'] == 'arm':
                exec("workload = %s('arm_%s', 'linux', '%s')" % (
                        app, options.arm_iset, options.spec_input))
            else:
                exec("workload = %s(buildEnv['TARGET_ISA', 'linux', '%s')" % (
                        app, options.spec_input))
            multiprocesses.append(workload.makeProcess())
        except:
            print("Unable to find workload for %s: %s" %
                  (buildEnv['TARGET_ISA'], app),
                  file=sys.stderr)
            sys.exit(1)

elif options.cmd:
    multiprocesses, numThreads = get_processes(options)
else:
    print("No workload specified. Exiting!\n", file=sys.stderr)
    sys.exit(1)


(CPUClass, test_mem_mode, FutureClass) = Simulation.setCPUClass(options)
CPUClass.numThreads = numThreads

# Check -- do not allow SMT with multiple CPUs
if options.smt and options.num_cpus > 1:
    fatal("You cannot use SMT with multiple CPUs!")

######################### Making System ########################################
np = options.num_cpus
system = System(cpu = [CPUClass(cpu_id=i) for i in range(np)],
                mem_mode = test_mem_mode,
                mem_ranges = [AddrRange(options.mem_size)],
                cache_line_size = options.cacheline_size)

if numThreads > 1:
    system.multi_thread = True

# Create a top-level voltage domain
system.voltage_domain = VoltageDomain(voltage = options.sys_voltage)

# Create a source clock for the system and set the clock period
system.clk_domain = SrcClockDomain(clock =  options.sys_clock,
                                   voltage_domain = system.voltage_domain)

# Create a CPU voltage domain
system.cpu_voltage_domain = VoltageDomain()

# Create a separate clock domain for the CPUs
system.cpu_clk_domain = SrcClockDomain(clock = options.cpu_clock,
                                       voltage_domain =
                                       system.cpu_voltage_domain)

# system.tgen = [TrafficGen(config_file=options.tgen_cfg_file) for i in
#                range(options.num_tgen)]

# If elastic tracing is enabled, then configure the cpu and attach the elastic
# trace probe
if options.elastic_trace_en:
    CpuConfig.config_etrace(CPUClass, system.cpu, options)

# All cpus belong to a common cpu_clk_domain, therefore running at a common
# frequency.
for cpu in system.cpu:
    cpu.clk_domain = system.cpu_clk_domain

# if ObjectList.is_kvm_cpu(CPUClass) or ObjectList.is_kvm_cpu(FutureClass):
#     if buildEnv['TARGET_ISA'] == 'x86':
#         system.kvm_vm = KvmVM()
#         for process in multiprocesses:
#             process.useArchPT = True
#             process.kvmInSE = True
#     else:
#         fatal("KvmCPU can only be used in SE mode with x86")

############################# Making Interupts #################################
MemConfig.config_mem(options, system)
if (options.arch == "same"):
    system.membus = SystemXBar()
else:
    system.system_port = system.membus.slave

for cpu in system.cpu:
    cpu.createInterruptController()
    cpu.interrupts[0].pio = system.membus.master
    cpu.interrupts[0].int_master = system.membus.slave
    cpu.interrupts[0].int_slave = system.membus.master

############################# Making Cache #####################################
for cpu in system.cpu:
    cpu.icache_port = system.membus.slave
    cpu.dcache_port = system.membus.slave

######################### Making Traffic #######################################
# Connect the traffic generatiors
# if options.arch == "distributed":
#     for i in range(options.num_tgen):
#         system.tgen[i].port = system.membus.slave
# if options.arch == "mixed":
#     for i in range(int(options.num_tgen/2)):
#         system.tgen[i].port = system.membus.slave
#     hh = system.hmc_host
#     if options.enable_global_monitor:
#         system.tgen[2].port = hh.lmonitor[2].slave
#         hh.lmonitor[2].master = hh.seriallink[2].slave
#         system.tgen[3].port = hh.lmonitor[3].slave
#         hh.lmonitor[3].master = hh.seriallink[3].slave
#     else:
#         system.tgen[2].port = hh.seriallink[2].slave
#         system.tgen[3].port = hh.seriallink[3].slave
#     # connect the system port even if it is not used in this example
# if options.arch == "same":
#     hh = system.hmc_host
#     for i in range(options.num_links_controllers):
#         if options.enable_global_monitor:
#             system.tgen[i].port = hh.lmonitor[i].slave
#         else:
#             system.tgen[i].port = hh.seriallink[i].slave

##############################Loading Works#####################################
# Sanity check
if options.simpoint_profile:
    if not ObjectList.is_noncaching_cpu(CPUClass):
        fatal("SimPoint/BPProbe should be done with an atomic cpu")
    if np > 1:
        fatal("SimPoint generation not supported with more than one CPUs")

for i in range(np):
    if options.smt:
        system.cpu[i].workload = multiprocesses
    elif len(multiprocesses) == 1:
        system.cpu[i].workload = multiprocesses[0]
    else:
        system.cpu[i].workload = multiprocesses[i]

    if options.simpoint_profile:
        system.cpu[i].addSimPointProbe(options.simpoint_interval)

    if options.checker:
        system.cpu[i].addCheckerCpu()

    if options.bp_type:
        bpClass = ObjectList.bp_list.get(options.bp_type)
        system.cpu[i].branchPred = bpClass()

    if options.indirect_bp_type:
        indirectBPClass = \
            ObjectList.indirect_bp_list.get(options.indirect_bp_type)
        system.cpu[i].branchPred.indirectBranchPred = indirectBPClass()

    system.cpu[i].createThreads()

#CacheConfig.config_cache(options, system)

config_filesystem(system, options)
root = Root(full_system = False, system = system)
Simulation.run(options, root, system, FutureClass)
