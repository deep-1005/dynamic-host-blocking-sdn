# Dynamic Host Blocking System — SDN Mininet Project

**Name:** Deeptha S | **SRN:** PES1UG24CS144 | **PES University**

---

## Problem Statement

Dynamically block hosts based on traffic behavior using an SDN controller (Ryu + OpenFlow 1.3).

The Ryu controller monitors packet rate per host in real time. If any host exceeds **20 packets within a 30-second window**, the controller automatically installs a high-priority DROP flow rule on the OVS switch — blocking that host from sending any further traffic until the next window reset.

---

## Topology

```
h1 (10.0.0.1) ─┐
h2 (10.0.0.2) ─┤
                s1 (OVS Switch / OpenFlow 1.3) ──── Ryu Controller (127.0.0.1:6633)
h3 (10.0.0.3) ─┤
h4 (10.0.0.4) ─┘
```

- 1 OVS switch, 4 hosts, 1 remote Ryu controller
- OpenFlow 1.3 protocol
- SingleSwitchTopo from Mininet

---

## How It Works

1. On switch connect, controller installs a **table-miss rule** (priority 0) — all unknown packets sent to controller
2. `packet_in` handler receives every packet and extracts the source MAC
3. Controller maintains a **per-MAC packet counter** that resets every 30 seconds
4. A live progress bar `[████░░░░] count/20` is logged per host in real time
5. At 15 packets → WARNING logged
6. At 21+ packets → controller calls `_block_host()`:
   - Installs a **DROP rule (priority 200, empty action list)** matching `eth_src` of the offending host
   - Switch drops all future packets from that host at line rate — controller no longer involved
7. Legitimate hosts continue to communicate normally via MAC learning and forwarding

### OpenFlow Concepts Used

| Concept | Implementation |
|---|---|
| `packet_in` event | Every unknown packet sent to controller via table-miss rule |
| MAC learning | `mac_to_port` dict maps MAC → port per switch |
| `flow_mod` | `_add_flow()` installs match+action rules on the switch |
| Match field | `eth_src` — identifies offending host by source MAC |
| Action = DROP | Empty action list `[]` — switch discards all matched packets |
| Priority 200 | Block rules override all forwarding rules (priority 0) |
| `OFPP_FLOOD` | Used when destination MAC is unknown |

---

## Files

| File | Purpose |
|---|---|
| `dynamic_blocker.py` | Ryu controller — packet_in handler, MAC learning, blocking logic |
| `topology.py` | Mininet topology — 1 switch, 4 hosts, remote controller |

---

## Setup and Installation

### Requirements

- Ubuntu 20.04 / 22.04
- Python 3.11
- Mininet
- Ryu Controller 4.34
- iperf, Wireshark (for testing)

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

# Fix eventlet compatibility issue with Ryu on Python 3.11
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

Expected startup output:
```
==============================================================
   DYNAMIC HOST BLOCKING SYSTEM — STARTED
==============================================================
   Blocking threshold : 20 packets
   Count reset every  : 30 seconds
   Warning at         : 15 packets
==============================================================
  [ INFO   ]  Waiting for switch to connect...
  [ SWITCH ]  Switch 1 connected successfully!
  [ RULE   ]  Default rule installed: send all packets to controller
  [ INFO   ]  System is ACTIVE — monitoring all traffic
```

### Terminal 2 — Start Mininet

```bash
sudo python3 ~/ryu-project/topology.py
```

Expected output:
```
========================================
  Hosts: h1=10.0.0.1  h2=10.0.0.2
         h3=10.0.0.3  h4=10.0.0.4
========================================
mininet>
```

---

## Test Scenarios

### Scenario 1 — Allowed vs Blocked Traffic

**Goal:** Show legitimate hosts communicate freely while a flooding host gets blocked.

#### Step 1 — Verify all hosts reachable (before any attack)

```
mininet> pingall
```

Expected:
```
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
```

#### Step 2 — Check flow table before attack (run in a separate terminal)

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Expected — only the table-miss rule:
```
priority=0  actions=CONTROLLER:65535
```

#### Step 3 — Simulate flood attack from h3

```
mininet> h3 ping -f h1 &
```

Watch controller log — packet counter climbs:
```
  [ PACKET ]  Host-3 [xx:xx] -> Host-1 [xx:xx] | [███████████████░░░░░] 15/20
  [WARNING ]  Host-3 is approaching the block limit!
  [ PACKET ]  Host-3 [xx:xx] -> Host-1 [xx:xx] | [████████████████████] 21/20
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  [ BLOCK  ]  HOST BLOCKED --> Host-3 [2a:54:bf:c8:08:06]
  [ BLOCK  ]  Reason  : Sent more than 20 packets
  [ BLOCK  ]  Action  : DROP rule installed on switch (priority 200)
  [ BLOCK  ]  Result  : ALL future packets from this host are dropped
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

Press `Ctrl+C` once block is confirmed in the log.

#### Step 4 — Verify h3 is blocked

```
mininet> h3 ping -c 3 h1
```

Expected:
```
3 packets transmitted, 0 received, 100% packet loss
```

#### Step 5 — Verify h1 and h2 still communicate normally (allowed)

```
mininet> h1 ping -c 5 h2
```

Expected:
```
5 packets transmitted, 5 received, 0% packet loss
```

#### Step 6 — Check flow table after attack

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Expected — DROP rule now appears:
```
priority=200, dl_src=2a:54:bf:c8:08:06  actions=drop
priority=0                               actions=CONTROLLER:65535
```

The `n_packets` counter on the DROP rule increases over time — the switch is discarding h3's packets in hardware without involving the controller at all.

---

### Scenario 2 — Normal vs Failure (iperf throughput + flow table)

**Goal:** Measure bandwidth — normal host vs blocked host, and observe flow table changes.

#### Step 1 — Clean restart

```
mininet> exit
```
```bash
sudo mn -c
```
Restart controller (Terminal 1) and topology (Terminal 2).

#### Step 2 — Measure normal throughput first (before any attack)

```
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 10
```

Expected:
```
[  1]  0.0-10.0 sec   ~113 MBytes   ~95 Mbits/sec
```

#### Step 3 — Trigger h3 block with controlled burst

```
mininet> h3 ping -c 25 -i 0.01 h1
```

Sends 25 packets fast enough to cross the 20-packet threshold. Confirm block in controller log.

#### Step 4 — Check flow table (separate terminal)

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

Expected:
```
priority=200, dl_src=<h3-mac>  actions=drop       ← h3 dynamically blocked
priority=0                     actions=CONTROLLER  ← table-miss rule
```

Run twice, 10 seconds apart — `n_packets` on the DROP rule increases each time, proving the switch is actively dropping h3's traffic.

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
sleep 10
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

#### Step 5 — iperf from blocked h3 (failure case)

```
mininet> h3 iperf -c 10.0.0.2 -t 5
```

Expected:
```
tcp connect failed: No route to host
```

#### Step 6 — iperf from h1 (normal case — still full speed)

```
mininet> h1 iperf -c 10.0.0.2 -t 5
```

Expected:
```
[  1]  0.0-5.0 sec   ~56 MBytes   ~95 Mbits/sec
```

#### Results Summary

| Host | Ping result | iperf throughput | Flow table entry |
|---|---|---|---|
| h1 (normal) | 0% packet loss, ~1ms RTT | ~95 Mbits/sec | Forwarding rule |
| h3 (blocked) | 100% packet loss | 0 Mbits/sec | DROP rule (priority 200) |

---


---

## Known Limitation & Design Note

The current implementation counts all outgoing packets per host. In a flood scenario, the reply host (h1) may also accumulate enough reply packets to get blocked alongside the attacker. For this demonstration, the threshold is intentionally set low (20 packets) to make the blocking behavior observable quickly. In a production deployment, the threshold would be set to 500–1000 packets per window, and reply traffic would be excluded from the count.

---


---

## References

1. Ryu SDN Framework Documentation — https://ryu.readthedocs.io
2. Mininet Walkthrough — http://mininet.org/walkthrough/
3. OpenFlow 1.3 Specification — https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
4. faucetsdn/ryu GitHub — https://github.com/faucetsdn/ryu
5. Open vSwitch Documentation — https://docs.openvswitch.org/
