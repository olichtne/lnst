"""
Implements scenario similar to regression_tests/phase1/
(3_vlans_over_{round_robin, active_backup}_bond.xml + 3_vlans_over_bond.py),
but 2 Vlans are used
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import VlanDevice
from lnst.Devices import BondDevice

class VlansOverBondRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1")
    m1.eth1 = DeviceReq(label="net1")

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        m1.bond = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
        m1.eth0.down()
        m1.eth1.down()
        m1.bond.slave_add(m1.eth0)
        m1.bond.slave_add(m1.eth1)
        m1.vlan1 = VlanDevice(realdev=m1.bond, vlan_id=10)
        m1.vlan2 = VlanDevice(realdev=m1.bond, vlan_id=20)

        m2.vlan1 = VlanDevice(realdev=m2.eth0, vlan_id=10)
        m2.vlan2 = VlanDevice(realdev=m2.eth0, vlan_id=20)

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.vlan1
        configuration.endpoint2 = m2.vlan1

        if "mtu" in self.params:
            m1.bond.mtu = self.params.mtu
            m2.eth0.mtu = self.params.mtu
            m1.vlan1.mtu = self.params.mtu
            m1.vlan2.mtu = self.params.mtu
            m2.vlan1.mtu = self.params.mtu
            m2.vlan2.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr_2 = "192.168.20"
        net_addr6_1 = "fc00:0:0:1"
        net_addr6_2 = "fc00:0:0:2"

        for i, m in enumerate([m1, m2]):
            m.vlan1.ip_add(ipaddress(net_addr_1 + "." + str(i+1) + "/24"))
            m.vlan1.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) + "/64"))
            m.vlan2.ip_add(ipaddress(net_addr_2 + "." + str(i+1) + "/24"))
            m.vlan2.ip_add(ipaddress(net_addr6_2 + "::" + str(i+1) + "/64"))

        m1.eth0.up()
        m1.eth1.up()
        m1.bond.up()
        m1.vlan1.up()
        m1.vlan2.up()
        m2.eth0.up()
        m2.vlan1.up()
        m2.vlan2.up()

        if "adaptive_rx_coalescing" in self.params:
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                dev.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                dev.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
            for dev in [m1.eth0, m1.eth1, m2.eth0]:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for m, d in [(m1, m1.eth0), (m1, m1.eth1), (m2, m2.eth0)]:
                m.run("tc qdisc replace dev %s root mq" % d.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m1.run("service irqbalance start")