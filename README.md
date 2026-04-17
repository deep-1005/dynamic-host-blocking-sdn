Dynamic Host Blocking System using SDN (Mininet + Ryu)
Student Details
Name: Deeptha S
SRN: PES1UG24CS144
Subject: Computer Networks
Problem Statement

Design and implement a system that dynamically detects and blocks malicious hosts based on abnormal traffic patterns using Software Defined Networking (SDN).

The Ryu controller monitors packet rates per host. If a host exceeds a threshold of 20 packets within a 30-second window, the controller installs a DROP flow rule on the switch to prevent further communication.

Objectives
Monitor network traffic in real time
Detect abnormal (high-rate) traffic behavior
Automatically mitigate attacks using SDN control logic
Ensure unaffected hosts continue normal communication
Network Topology
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤
               s1 ─── Ryu Controller (port 6633)
h3 (10.0.0.3) ─┤
h4 (10.0.0.4) ─┘
Single Open vSwitch (s1)
Four hosts (h1–h4)
Remote Ryu controller
OpenFlow 1.3 protocol
System Design
Traffic Handling
Switch forwards all packets to controller (table-miss rule)
Controller inspects each packet (Packet-In event)
Packet count maintained per source MAC address
Blocking Logic
Threshold: 20 packets
Monitoring window: 30 seconds
If threshold exceeded:
Install flow rule: match = eth_src
Action: DROP
Priority: 200
Reset Mechanism
Packet counters reset every 30 seconds
Allows temporary spikes without permanent blocking
Setup and Installation
Requirements
Ubuntu 20.04 / 22.04
Python 3.11
Mininet
Ryu Controller 4.34
Installation Steps
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv mininet iperf wireshark

mkdir ~/ryu-project && cd ~/ryu-project
python3.11 -m venv venv
source venv/bin/activate

pip install setuptools==67.6.0
pip install eventlet==0.33.3
pip install dnspython==2.6.1
pip install ryu

# Fix eventlet compatibility issue
sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
~/ryu-project/venv/lib/python3.11/site-packages/ryu/app/wsgi.py
Verify Installation
ryu-manager --version

Expected output:

ryu-manager 4.34
Running the Project
Terminal 1 — Start Controller
cd ~/ryu-project
source venv/bin/activate
ryu-manager dynamic_blocker.py --verbose
Terminal 2 — Start Mininet
sudo python3 ~/ryu-project/topology.py
Test Scenarios
Scenario 1: Allowed vs Blocked Traffic
Step 1 — Verify Connectivity
mininet> pingall

Expected result:
All hosts reachable with 0% packet loss

Step 2 — Check Flow Table (Before Attack)
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
Step 3 — Simulate Flood Attack
mininet> h3 ping -f h1 &
Rapid packet generation triggers threshold
Controller logs show packet count increasing
Host gets blocked after threshold is exceeded
Step 4 — Verify Blocked Host
mininet> h3 ping -c 3 h1

Expected result:
100% packet loss

Step 5 — Verify Other Hosts
mininet> h1 ping -c 5 h2

Expected result:
0% packet loss

Step 6 — Verify Flow Rule
sudo ovs-ofctl -O OpenFlow13 dump-flows s1

Expected output includes:

priority=200,dl_src=<MAC> actions=drop
Scenario 2: Normal vs Failure (Throughput Analysis)
Step 1 — Clean Restart
mininet> exit
sudo mn -c

Restart controller and topology

Step 2 — Measure Normal Throughput
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 10

Expected result:
Throughput around 90–100 Mbits/sec

Step 3 — Trigger Host Blocking
mininet> h3 ping -f h1 &

Wait until controller logs indicate host is blocked

Step 4 — Test Blocked Host Throughput
mininet> h3 iperf -c 10.0.0.2 -t 5

Expected result:

0.00 Mbits/sec OR
Connection failure
Step 5 — Verify Normal Host Performance
mininet> h1 iperf -c 10.0.0.2 -t 5

Expected result:
Throughput remains 90–100 Mbits/sec

Expected Outputs
Controller Logs
[PACKET] Host-X -> Host-Y | count=20
[PACKET] Host-X -> Host-Y | count=21

BLOCKED HOST: <MAC address>
Flow Table
priority=200,dl_src=<MAC> actions=drop
priority=0 actions=CONTROLLER
Code Structure
Controller Implementation

File: dynamic_blocker.py

Features:

Packet counting per host
Threshold-based blocking
Flow rule installation
Logging and monitoring
Network Topology

File: topology.py

Single switch topology
Remote controller connection
Four hosts configuration
Results and Observations
Normal traffic flows without interruption
Flooding attack is detected quickly
Malicious host is blocked automatically
Other hosts remain unaffected
Throughput remains stable for legitimate hosts
Conclusion

This project demonstrates how SDN can be used to implement real-time network security mechanisms. By separating the control plane from the data plane, the controller can dynamically enforce policies such as traffic blocking based on observed behavior.

References
Ryu Documentation: https://ryu.readthedocs.io
Mininet Walkthrough: http://mininet.org/walkthrough/
OpenFlow 1.3 Specification: https://opennetworking.org
Ryu GitHub Repository: https://github.com/faucetsdn/ryu
