from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from collections import defaultdict
import time

class DynamicHostBlocker(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DynamicHostBlocker, self).__init__(*args, **kwargs)
        self.mac_to_port   = {}
        self.packet_count  = defaultdict(int)
        self.blocked_hosts = set()
        self.THRESHOLD     = 20
        self.last_reset    = time.time()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp      = ev.msg.datapath
        ofproto = dp.ofproto
        parser  = dp.ofproto_parser
        # Send ALL packets to controller — no flow rules installed
        match   = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, match, actions)
        self.logger.info("Switch %s connected", dp.id)

    def _add_flow(self, dp, priority, match, actions, idle_timeout=0):
        parser  = dp.ofproto_parser
        ofproto = dp.ofproto
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod  = parser.OFPFlowMod(datapath=dp, priority=priority,
                                  idle_timeout=idle_timeout,
                                  match=match, instructions=inst)
        dp.send_msg(mod)

    def _block_host(self, dp, src_mac):
        """Install DROP rule — highest priority, no actions = drop"""
        parser = dp.ofproto_parser
        match  = parser.OFPMatch(eth_src=src_mac)
        self._add_flow(dp, 200, match, [])
        self.blocked_hosts.add(src_mac)
        self.logger.warning("*** BLOCKED HOST: %s exceeded %d packets ***",
                             src_mac, self.THRESHOLD)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
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

        # Reset counts every 30 seconds
        now = time.time()
        if now - self.last_reset > 30:
            self.packet_count.clear()
            self.last_reset = now
            self.logger.info("[RESET] Packet counts cleared")

        # Skip already blocked hosts silently
        if src in self.blocked_hosts:
            return

        # Count every packet from this source
        self.packet_count[src] += 1
        self.logger.info("[PKT] %s -> %s | count=%d",
                         src, dst, self.packet_count[src])

        # Block if threshold exceeded
        if self.packet_count[src] > self.THRESHOLD:
            self._block_host(dp, src)
            return

        # MAC learning — just forward, no flow rules installed
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)
        actions  = [parser.OFPActionOutput(out_port)]

        # Send this packet out — but do NOT install a flow rule
        out = parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=msg.data)
        dp.send_msg(out)
