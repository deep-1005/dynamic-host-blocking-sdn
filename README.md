# Dynamic Host Blocking System — SDN Mininet Project

## Student Details
- **Name:** Deeptha S
- **SRN:** PES1UG24CS144
- **Subject:** SDN Mininet-based Simulation (Orange Problem)

---

## Problem Statement
Dynamically block hosts based on traffic behavior using an SDN controller.
The Ryu controller monitors packet rate per host. If any host exceeds a
threshold of 20 packets within a 30-second window, the controller
automatically installs a DROP flow rule on the switch to block that host
from sending any further traffic.

---

## Topology
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤
s1 ──── Ryu Controller (port 6633)
h3 (10.0.0.3) ─┤
h4 (10.0.0.4) ─┘
- 1 OVS switch, 4 hosts, 1 remote Ryu controller
- OpenFlow 1.3

---

## How It Works
1. All packets are sent to the Ryu controller via a table-miss flow rule
2. Controller counts packets per source MAC address
3. If a host exceeds 20 packets → controller installs a DROP rule (priority 200)
4. Blocked host cannot send any further traffic
5. Packet counts reset every 30 seconds

---

## Setup and Installation

### Requirements
- Ubuntu 20.04 / 22.04
- Python 3.11
- Mininet
- Ryu Controller 4.34

### Install Dependencies
```bash
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
```

### Verify Ryu
```bash
ryu-manager --version
# Expected: ryu-manager 4.34
```

---

## Running the Project

### Terminal 1 — Start Ryu Controller
```bash
cd ~/ryu-project
source venv/bin/activate
ryu-manager dynamic_blocker.py --verbose
```

### Terminal 2 — Start Mininet
```bash
sudo python3 ~/ryu-project/topology.py
```

---

## Test Scenarios

### Scenario 1 — Normal Traffic (should succeed)
```bash
mininet> h1 ping h2 -c 5
```
**Expected:** 5 packets transmitted, 5 received, 0% packet loss

### Scenario 2 — Flood Attack (host gets blocked)
```bash
mininet> h4 ping -i 0.2 -c 200 h1
```
**Expected:** Replies stop after ~20 packets. Controller logs:
*** BLOCKED HOST: xx:xx:xx:xx exceeded 20 packets ***

### Verify Block Rule in Flow Table
```bash
mininet> sh ovs-ofctl dump-flows s1
```
**Expected:** Rule with `actions=drop` for h4's MAC address

### Verify Blocked Host Cannot Communicate
```bash
mininet> h4 ping h1 -c 3
```
**Expected:** 3 packets transmitted, 0 received, 100% packet loss

### Performance Test (iperf)
```bash
mininet> h2 iperf -s &
mininet> h3 iperf -c 10.0.0.2
```

---

## Expected Output

### Controller Terminal (Terminal 1)
[PKT] 46:e0:52:f1:74:77 -> 4e:38:14:be:a2:79 | count=20
[PKT] 46:e0:52:f1:74:77 -> 4e:38:14:be:a2:79 | count=21
*** BLOCKED HOST: 46:e0:52:f1:74:77 exceeded 20 packets ***

### Flow Table After Blocking
priority=200,dl_src=46:e0:52:f1:74:77 actions=drop
priority=0 actions=CONTROLLER:65535

---

## Evaluation Criteria Coverage

| Component | What was demonstrated |
|---|---|
| Problem Understanding & Setup | Mininet topology, Ryu controller, OpenFlow 1.3 |
| SDN Logic & Flow Rule Implementation | packet_in handler, match on eth_src, DROP action |
| Functional Correctness | Normal ping works, flood gets blocked, verified with dump-flows |
| Performance Observation | iperf bandwidth, ping latency, packet loss statistics |
| Validation | h4 ping after blocking = 100% loss (regression test) |

---

## References
- Ryu SDN Framework: https://ryu.readthedocs.io
- Mininet Walkthrough: http://mininet.org/walkthrough/
- OpenFlow 1.3 Specification: https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
- faucetsdn/ryu GitHub: https://github.com/faucetsdn/ryu
