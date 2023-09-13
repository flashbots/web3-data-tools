# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_mev_boost.ipynb.

# %% auto 0
__all__ = ['FIRST_POS_SLOT', 'fb', 'mp', 'mr', 'mf', 'ed', 'bn', 'ul', 'ag', 'ae', 'sr', 'wm', 'all_relays', 'Relay']

# %% ../nbs/02_mev_boost.ipynb 4
from bisect import bisect_left
from functools import cache

import requests

from .web3 import MultiRPCWeb3, FIRST_POS_BLOCK
from .core import interpolation_search

# %% ../nbs/02_mev_boost.ipynb 6
FIRST_POS_SLOT = 4700013 

# %% ../nbs/02_mev_boost.ipynb 7
fb = "https://boost-relay.flashbots.net"
# et = "https://bloxroute.ethical.blxrbdn.com"
mp = "https://bloxroute.max-profit.blxrbdn.com"
mr = "https://bloxroute.regulated.blxrbdn.com"
mf = "https://mainnet-relay.securerpc.com"
ed = "https://relay.edennetwork.io"
bn = "https://builder-relay-mainnet.blocknative.com"
# rl = "https://relayooor.wtf"
ul = "https://relay.ultrasound.money"
ag = "https://agnostic-relay.net"
ae = "https://mainnet.aestus.live"
ae = "https://aestus.live"
sr = "https://mainnet-relay.securerpc.com/"
wm = "https://relay.wenmerge.com/"

# %% ../nbs/02_mev_boost.ipynb 8
all_relays = [fb, mp, mr, mf, ed, bn, ul, ag, ae]

# %% ../nbs/02_mev_boost.ipynb 10
class Relay:
    """A class for interacting with a relay's API"""

    def __init__(self, path, *rpcs):
        """path is the base url of the relay's API"""
        self.path = path
        if len(rpcs)==1 and isinstance(rpcs[0], MultiRPCWeb3):
            self.w3 = rpcs[0]
        else:
            self.w3 = MultiRPCWeb3.from_rpcs(*rpcs)
        self.calls = 0
        self.slot2block_cache = {}

    @cache
    def proposer_payload_delivered(self, limit=None, cursor=None, block_number=None, order_by=None):
        """Get proposer payloads delivered by the relay"""
        self.calls += 1
        path = f'{self.path}/relay/v1/data/bidtraces/proposer_payload_delivered?'
        params = [f'limit={limit}', f'cursor={cursor}', f'block_number={block_number}', f'order_by={order_by}']
        params = [x for x, y in zip(params, [limit, cursor, block_number, order_by]) if y is not None]
        path += '&'.join(params)
        r = requests.get(path)
        out = r.json()
        for o in out:
            o['slot'] = int(o['slot'])
            o['block_number'] = int(o['block_number'])
            o['value'] = float(o['value'])
            o['gas_used'] = int(o['gas_used'])
            o['gas_limit'] = int(o['gas_limit'])
            o['num_tx'] = int(o['num_tx'])
        return out
    
    def get_first_slot(self, lo=None, hi=None):
        if lo is None:
            lo = FIRST_POS_SLOT
        self.getitem = self.slot_has_data
        first_slot = bisect_left(self, 1, lo=lo, hi=hi)
        self.getitem = self.get_slot_payload
        return first_slot
    
    def find_slot_at_block_number(self, block_number, low=None, high=None, how='left'):
        if low is None:
            low = self.get_first_slot()
        self.getitem = self.get_slot_block_number
        if self[low] > block_number:
            return None
        out = interpolation_search(self, block_number, low=low, high=high, how=how)
        self.getitem = self.get_slot_payload
        return out
    
    def find_slot_at_timestamp(self, timestamp, low_slot=None, high_slot=None, how='left'):
        if low_slot is None:
            low_slot = self.get_first_slot()
        low_block = self.get_slot_block_number(low_slot)
        if high_slot is None:
            high_block = None
        else:
            high_block = self.get_slot_block_number(high_slot)
        if self.w3[low_block] > timestamp:
            return None
        block_number = interpolation_search(self.w3, timestamp, low=low_block, high=high_block, how=how)
        out = self.find_slot_at_block_number(block_number, low=low_slot, high=high_slot, how=how)
        return out

    def get_slot_payload(self, slot):
        out = self.proposer_payload_delivered(limit=1, cursor=slot)
        if len(out)>0:
            return out[0]
        return None
    
    def slot_has_data(self, slot):
        return not self.get_slot_payload(slot) is None
    
    def get_slot_block_number(self, slot):
        if slot in self.slot2block_cache:
            return self.slot2block_cache[slot]
        payloads = self.proposer_payload_delivered(limit=100, cursor=slot)
        for p0, p1 in zip(payloads[1:], payloads[:-1]):
            block_number = p0['block_number']
            for s in range(p0['slot'], p1['slot']):
                self.slot2block_cache[s] = block_number
        block_number = payloads[0]['block_number']
        for s in range(payloads[0]['slot'], slot+1):
            self.slot2block_cache[s] = block_number
        return block_number

    def getitem(self, slot):
        return self.get_slot_payload(slot)

    def __getitem__(self, slot):
        return self.getitem(slot)

    def __len__(self):
        return int(self.proposer_payload_delivered(limit=1)[0]['slot'])
    
    def iter_payloads_in_slot_range(self, min_slot, max_slot):
        cursor = max_slot
        for _ in range((max_slot-min_slot)//100+1):
            payloads = self.proposer_payload_delivered(limit=100, cursor=cursor)
            for payload in payloads:
                cursor = payload['slot']
                if cursor < min_slot:
                    return
                yield payload
    
    def get_payloads_between_timestamps(self, min_timestamp, max_timestamp, min_block_number=None, max_block_number=None):
        min_slot = self.find_slot_at_timestamp(min_timestamp, how='right')
        if min_slot is None:
            return []
        max_slot = self.find_slot_at_timestamp(max_timestamp, low_slot=min_slot, how='left')
        return list(self.iter_payloads_in_slot_range(min_slot, max_slot))

    def get_payloads_between_block_numbers(self, min_block_number, max_block_number):
        min_slot = self.find_slot_at_block_number(min_block_number, how='right')
        if min_slot is None:
            return []
        max_slot = self.find_slot_at_block_number(max_block_number, low=min_slot, how='left')
        return list(self.iter_payloads_in_slot_range(min_slot, max_slot))
