#
# Wolfinch Auto trading Bot screener
#  *** options iv under 5
#  *** option selling screener, maximum profit 
#
#  Copyright: (c) 2017-2021 Joshith Rayaroth Koderi
#  This file is part of Wolfinch.
# 
#  Wolfinch is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  Wolfinch is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with Wolfinch.  If not, see <https://www.gnu.org/licenses/>.

# from decimal import Decimal
import re
from .screener_base import Screener
import time
from datetime import datetime
import notifiers

from utils import getLogger

log = getLogger("OPT_IV")
log.setLevel(log.DEBUG)

class OPT_IV(Screener):
    def __init__(self, name="OPT_IV", ticker_kind="ALL", interval=24*60*60, multiplier=1, data="", notify=None, **kwarg):
        log.info ("init: name: %s ticker_kind: %s interval: %d multiplier: %d data_src_name: %s"%(name, ticker_kind, interval, multiplier, data))
        super().__init__(name, ticker_kind, interval)
        self.multiplier = multiplier
        self.data_src_name = data
        self.notify_kind = notify
        self.filtered_list = {} #li
    def update(self, sym_list, ticker_stats_g):
        #we don't update data_src_name here. Rather self.data_src_name is our data_src_name source
        try:
            t_data = ticker_stats_g.get(self.data_src_name)
            if not t_data:
                log.error ("ticker data_src_name from screener %s not updated"%(self.data_src_name))
                return False
            #make sure all data_src_name available for our list 
            ## TODO: FIXME: optimize this
            if False == t_data.get("__updated__"):
                log.error ("data_src_name is still being updated")
                return False
            return True
        except Exception as e:
            log.critical("exception while get data_src_name e: %s"%(e))
            return False
    def screen(self, sym_list, ticker_stats_g):
        # Screen: Total_cash_balance > cur_market_cap
        #1.get data_src_name from self.data_src_name 
        ticker_stats = ticker_stats_g.get(self.data_src_name)
        if not ticker_stats:
            raise

        #2. for each sym, if cash_pos > market_cap -> add filtered l
        self.filtered_list = {}
        now = int(time.time())
        try:
            fs_l = []
            for sym in sym_list:
                sym_d = ticker_stats[sym]
                # log.info("sym_d: %s \n"%(sym_d))
                if len(sym_d) == 0:
                    continue
                puts = sym_d[0].get("puts")
                if puts :
                    i=0
                    for pc in puts:
                        #find the first in-the-money. and use the strike below that. 
                        if pc["inTheMoney"]:
                            break;
                        i+=1
                    pc = puts[i]
                    iv = round(pc["impliedVolatility"], 2)
                    strike = pc["strike"]
                    oi = pc["openInterest"]
                    price = round(pc["lastPrice"], 2)
                    c_sym = pc["contractSymbol"]
                    exp = c_sym[len(sym):len(sym)+6]
                    fs  = {"symbol": sym, "time": now,
                            "strike": strike,
                            "price": price,
                            "iv": iv,
                            "expiry": exp,
                            "oi": oi,
                            }
                    log.info ('new sym found by screener: %s info:  %s'%(sym, fs))
                    fs_l.append(fs)
                    # if self.notify_kind:
                    #     notify_msg = {"symbol": fs["symbol"],
                    #                     "cur_mcap": "%s)"%(mcap_s),
                    #                     "total_cash": "%s"%(tcash_s)}
                        # notifiers.notify(self.notify_kind, self.name, notify_msg)
            #now that we have list of opt. sort the list and get only top 25
            fs_l.sort(reverse=True, key=lambda e: e["iv"])
            self.filtered_list = {} #clear list
            for fs in fs_l[:25]:
                self.filtered_list [fs[sym]] = fs
        except Exception as e:
            log.critical("exception while get screen e: %s"%(e))
    def get_screened(self):
#         ft = [
#          {"symbol": "aapl", "strike": 2.5, "price": 10.2, "iv": "1.4", "expiry": "200511", "oi": "20", "time": "4"},
#              ]
        fmt = {"symbol": "Symbol", "time": "Time", "strike": "Strike",
         "price": "Price", "iv": "IV", "oi": "OI", "expiry": "Expiry"}
        return [fmt]+list(self.filtered_list.values())

#EOF
