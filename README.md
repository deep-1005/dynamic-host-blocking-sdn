Dynamic Host Blocking System — SDN Mininet Project
Student Details
Name: Deeptha S
SRN: PES1UG24CS144
Subject: Computer Networks
Problem Statement

Dynamically block hosts based on traffic behavior using an SDN controller.
The Ryu controller monitors packet rate per host. If any host exceeds a
threshold of 20 packets within a 30-second window, the controller
automatically installs a DROP flow rule on the switch to block that host
from sending any further traffic.

Topology
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤
s1 ──── Ryu Controller (port 6633)
h3 (10.0.0.3) ─┤
h4 (10.0.0.4) ─┘
1 OVS switch, 4 hosts, 1 remote Ryu controller
OpenFlow 1.3
How It Works
All packets are sent to the controller via a table-miss flow rule
Controller counts packets per source MAC address
If a host exceeds 20 packets → DROP rule installed (priority 200)
Blocked host cannot send any further traffic
Packet counts reset every 30 seconds
Setup and Installation
Requirements
Ubuntu 20.04 / 22.04
Python 3.11
Mininet
Ryu Controller 4.34
Install Dependencies
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv mininet iperf wireshark

mkdir ~/ryu-project && cd ~/ryu-project
python3.11 -m venv venv
source venv/bin/activate

pip install setuptools==67.6.0
pip install eventlet==0.33.3
pip install dnspython==2.6.1
pip install ryu

# Fix eventlet compatibility patch
sed -i 's/from eventlet.wsgi import ALREADY_HANDLED/ALREADY_HANDLED = b""/' \
    ~/ryu-project/venv/lib/python3.11/site-packages/ryu/app/wsgi.py
Verify Ryu
ryu-manager --version

Expected: ryu-manager 4.34

Running the Project
Terminal 1 — Start Ryu Controller
cd ~/ryu-project
source venv/bin/activate
ryu-manager dynamic_blocker.py --verbose
Terminal 2 — Start Mininet
sudo python3 ~/ryu-project/topology.py
Test Scenarios
Scenario 1 — Allowed vs Blocked
Step 1 — Verify Connectivity
mininet> pingall

Expected: 0% packet loss

Step 2 — Check Flow Table (Before Attack)
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
Step 3 — Simulate Flood Attack (h3)
mininet> h3 ping -f h1 &
Flood ping generates rapid traffic
Controller detects threshold breach
Host gets BLOCKED
Step 4 — Verify Block
mininet> h3 ping -c 3 h1

Expected: 100% packet loss

Step 5 — Verify Other Hosts
mininet> h1 ping -c 5 h2

Expected: 0% packet loss

Step 6 — Verify Flow Rule
sudo ovs-ofctl -O OpenFlow13 dump-flows s1

Expected:
priority=200, dl_src=<h3-mac> actions=drop

Scenario 2 — Normal vs Failure (iperf)
Step 1 — Clean Restart
mininet> exit
sudo mn -c
Step 2 — Normal Throughput
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 10

Expected: ~90–100 Mbits/sec

Step 3 — Trigger Block
mininet> h3 ping -f h1 &

Wait until controller shows BLOCKED

Step 4 — Test Blocked Host
mininet> h3 iperf -c 10.0.0.2 -t 5

Expected:

0.00 Mbits/sec
OR connection failure
Step 5 — Verify Normal Host
mininet> h1 iperf -c 10.0.0.2 -t 5

Expected: ~90–100 Mbits/sec

Expected Output
Controller Terminal
[PKT] xx:xx:xx -> yy:yy:yy | count=20
[PKT] xx:xx:xx -> yy:yy:yy | count=21
*** BLOCKED HOST ***
Flow Table After Blocking
priority=200,dl_src=<MAC> actions=drop
priority=0 actions=CONTROLLER:65535
Code Files
dynamic_blocker.py — Controller logic
topology.py — Mininet topology
Evaluation Criteria Coverage
Component	Description
Setup	Mininet + Ryu + OpenFlow
Logic	Packet counting and blocking
Correctness	Attack blocked, normal traffic allowed
Performance	iperf throughput maintained
Validation	Blocked host shows 100% packet loss
References
Ryu SDN Framework: https://ryu.readthedocs.io
Mininet Walkthrough: http://mininet.org/walkthrough/
OpenFlow Specification: https://opennetworking.org
Ryu GitHub: https://github.com/faucetsdn/ryu
