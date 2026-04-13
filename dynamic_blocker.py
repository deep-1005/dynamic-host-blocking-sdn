from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from collections import defaultdict
import time

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
THRESHOLD    = 20   # block after this many packets
RESET_WINDOW = 30   # reset counts every 30 seconds
WARN_AT      = 15   # warn when count hits this
# ─────────────────────────────────────────────

def print_banner():
    print("\n" + "="*62)
    print("   DYNAMIC HOST BLOCKING SYSTEM — STARTED")
    print("="*62)
    print(f"   Blocking threshold : {THRESHOLD} packets")
    print(f"   Count reset every  : {RESET_WINDOW} seconds")
    print(f"   Warning at         : {WARN_AT} packets")
    print("="*62 + "\n")

def log(tag, msg):
    ts = time.strftime("%H:%M:%S")
    tags = {
        "INFO"   : "[ INFO   ]",
        "PKT"    : "[ PACKET ]",
        "WARN"   : "[WARNING ]",
        "BLOCK"  : "[ BLOCK  ]",
        "RESET"  : "[ RESET  ]",
        "SWITCH" : "[ SWITCH ]",
        "FORWARD": "[FORWARD ]",
        "RULE"   : "[ RULE   ]",
    }
    label = tags.get(tag, f"[{tag}]")
    print(f"  {ts}  {label}  {msg}")


class DynamicHostBlocker(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DynamicHostBlocker, self).__init__(*args, **kwargs)
        self.mac_to_port   = {}
        self.packet_count  = defaultdict(int)
        self.blocked_hosts = set()
        self.host_labels   = {}   # MAC -> "Host-1", "Host-2" etc
        self.last_reset    = time.time()
        self.total_blocked = 0
        self.total_packets = 0
        print_banner()
        log("INFO", "Waiting for switch to connect...")

    def get_name(self, mac):
        """Give each MAC address a friendly readable name"""
        if mac not in self.host_labels:
            n = len(self.host_labels) + 1
            self.host_labels[mac] = f"Host-{n}"
        return f"{self.host_labels[mac]} [{mac}]"

    def _add_flow(self, dp, priority, match, actions, idle_timeout=0):
        """Install a flow rule on the switch"""
        parser  = dp.ofproto_parser
        ofproto = dp.ofproto
        inst = [parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod  = parser.OFPFlowMod(
                    datapath=dp, priority=priority,
                    idle_timeout=idle_timeout,
                    match=match, instructions=inst)
        dp.send_msg(mod)

    def _block_host(self, dp, src_mac):
        """Install a DROP rule for a misbehaving host"""
        parser = dp.ofproto_parser
        match  = parser.OFPMatch(eth_src=src_mac)
        self._add_flow(dp, 200, match, [])  # empty actions = DROP
        self.blocked_hosts.add(src_mac)
        self.total_blocked += 1

        print("\n  " + "!" * 58)
        log("BLOCK", f"HOST BLOCKED --> {self.get_name(src_mac)}")
        log("BLOCK", f"Reason  : Sent more than {THRESHOLD} packets")
        log("BLOCK", f"Action  : DROP rule installed on switch (priority 200)")
        log("BLOCK", f"Result  : ALL future packets from this host are dropped")
        log("BLOCK", f"Total hosts blocked so far: {self.total_blocked}")
        print("  " + "!" * 58 + "\n")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """When switch connects: install default table-miss rule"""
        dp      = ev.msg.datapath
        ofproto = dp.ofproto
        parser  = dp.ofproto_parser
        match   = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, match, actions)
        print()
        log("SWITCH", f"Switch {dp.id} connected successfully!")
        log("RULE",   "Default rule installed: send all packets to controller")
        log("INFO",   "System is ACTIVE — monitoring all traffic\n")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """Called for every packet — core logic lives here"""
        msg     = ev.msg
        dp      = msg.datapath
        ofproto = dp.ofproto
        parser  = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        src  = eth.src
        dst  = eth.dst
        dpid = dp.id

        self.total_packets += 1

        # ── Reset counts every RESET_WINDOW seconds ──
        now = time.time()
        if now - self.last_reset > RESET_WINDOW:
            self.packet_count.clear()
            self.last_reset = now
            print()
            log("RESET", f"Monitoring window reset at {time.strftime('%H:%M:%S')}")
            log("RESET", "All packet counts cleared — fresh window started")
            log("INFO",  f"Total packets seen: {self.total_packets} | "
                         f"Total hosts blocked: {self.total_blocked}\n")

        # ── Skip already blocked hosts ──
        if src in self.blocked_hosts:
            return

        # ── Count this packet ──
        self.packet_count[src] += 1
        count = self.packet_count[src]

        # ── Progress bar ──
        filled = int((count / THRESHOLD) * 20)
        filled = min(filled, 20)
        bar    = "█" * filled + "░" * (20 - filled)

        # ── Warning when approaching limit ──
        if count == WARN_AT:
            print()
            log("WARN", f"{self.get_name(src)} is approaching the block limit!")
            log("WARN", f"Count: [{bar}] {count}/{THRESHOLD} — watch this host!")
            print()
        else:
            log("PKT", f"{self.get_name(src)} -> {self.get_name(dst)} "
                       f"| [{bar}] {count}/{THRESHOLD}")

        # ── Block if over threshold ──
        if count > THRESHOLD:
            self._block_host(dp, src)
            return

        # ── MAC learning ──
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)

        if out_port == ofproto.OFPP_FLOOD:
            log("FORWARD", f"Destination unknown — flooding to all ports")
        else:
            log("FORWARD", f"Sending to port {out_port} -> {self.get_name(dst)}")

        # ── Forward the packet ──
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=msg.data)
        dp.send_msg(out)
