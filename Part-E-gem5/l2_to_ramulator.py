import os
import sys
import m5
from m5.objects import *

# -----------------------------
# Add Ramulator2 and cache paths
# -----------------------------
sys.path.insert(0, "/home/mounika/ramulator2/python")
import ramulator

# -----------------------------
# Cache definitions
# -----------------------------
class L1ICache(Cache):
    size = "16KiB"
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    size = "64KiB"
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    size = "256KiB"
    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports

# -----------------------------
# System
# -----------------------------
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()

system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MiB")]

# -----------------------------
# CPU
# -----------------------------
system.cpu = X86TimingSimpleCPU()

# L1 caches
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

# -----------------------------
# L2 hierarchy
# -----------------------------
system.l2bus = L2XBar()

system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

system.l2cache = L2Cache()
system.l2cache.connectCPUSideBus(system.l2bus)

# Memory bus
system.membus = SystemXBar()

# -----------------------------
# CommMonitor
# -----------------------------
system.monitor = CommMonitor()

system.l2cache.mem_side = system.monitor.cpu_side_port
system.monitor.mem_side_port = system.membus.cpu_side_ports

# -----------------------------
# Ramulator2 DDR4
# -----------------------------
ddr4 = ramulator.dram.DDR4(
    org_preset="DDR4_8Gb_x8",
    timing_preset="DDR4_3200AA",
    rank=1,
)

ctrl = ramulator.controller.GenericDDR(
    dram=ddr4,
    scheduler=ramulator.scheduler.FRFCFS(),
    refresh_manager=ramulator.refresh_manager.AllBank(),
    row_policy=ramulator.row_policy.Open(),
    addr_mapper=ramulator.addr_mapper.RoBaRaCoCh(),
)

memsys = ramulator.memory_system.GenericDRAM(
    clock_ratio=3,
    controllers=[ctrl],
    channel_mapper=ramulator.channel_mapper.CacheLineInterleave(),
)

system.ram = Ramulator2(
    ramulator_config=ramulator.gem5._build_config(memsys)
)

system.ram.range = system.mem_ranges[0]
system.ram.port = system.membus.mem_side_ports

# -----------------------------
# Interrupts
# -----------------------------
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

# -----------------------------
# Workload
# -----------------------------
thispath = os.path.dirname(os.path.realpath(__file__))
binary = os.path.join(
    thispath,
    "../tests/test-progs/hello/bin/x86/linux/hello"
)

system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# -----------------------------
# Run
# -----------------------------
root = Root(full_system=False, system=system)
m5.instantiate()

print("Starting simulation...")
exit_event = m5.simulate()

print(f"Exited @ tick {m5.curTick()} because {exit_event.getCause()}")
