from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import SingleSwitchTopo
from mininet.log import setLogLevel
from mininet.cli import CLI

def run():
    setLogLevel('info')
    topo = SingleSwitchTopo(4)
    net  = Mininet(topo=topo, switch=OVSSwitch,
                   controller=RemoteController('c0', ip='127.0.0.1', port=6633))
    net.start()
    print("\n========================================")
    print("  Hosts: h1=10.0.0.1  h2=10.0.0.2")
    print("         h3=10.0.0.3  h4=10.0.0.4")
    print("========================================\n")
    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()
