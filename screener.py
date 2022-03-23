#! /usr/bin/env python3
'''
# Wolfinch Stock Screener
# Desc: Main File implements Screener Entry points
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
'''

import sys
import os
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "../wolfinch/pkgs"))

import time
import traceback
import argparse
from decimal import getcontext
import random
import logging
from  strategies import Configure
import notifiers
from tickers_data import get_all_ticker_lists
import ui
import gc

from utils import getLogger, readConf

log = getLogger("Screener")
log.setLevel(logging.ERROR)

# mpl_logger = logging.getLogger('matplotlib')
# mpl_logger.setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(log.WARNING)

ScreenerConfig = None
ticker_import_time = 0
YF = None

# global Variables
MAIN_TICK_DELAY = 1  # 500*4 milli

def screener_init():
    global YF, ScreenerConfig
    # seed random
    random.seed()

    # print ("config: %s"%(ScreenerConfig))
    notifier = ScreenerConfig.get("notifier")
    if notifier != None:
        if False == notifiers.init(notifier):
            log.critical("notifier init failed")
            return False
    register_screeners(ScreenerConfig.get("strategies"))
    
    # setup ui if required
    if ScreenerConfig["ui"]["enabled"]:
        log.info("ui init")
        if False == ui.ui_init(port=ScreenerConfig["ui"].get("port"), get_data_cb=get_screener_data) :
            log.critical("unable to setup ui!! ")
            print("unable to setup UI!!")
            sys.exit(1)

def screener_end():
    log.info("Finalizing Screener")

    # stop stats thread
    log.info("waiting to stop stats thread")
    notifiers.end()
    ui.ui_end()
    log.info("all cleanup done.")

def screener_main():
    """
    Main Function for Screener
    """
    sleep_time = MAIN_TICK_DELAY
    gc_time = 0
    while True:
        cur_time = time.time()
        update_data()
        process_screeners()
        if gc_time + 6*60*60 < int(time.time()):
            log.info("force garbage collect")
            gc.collect()
            gc_time = int(time.time())
        # '''Make sure each iteration take exactly LOOP_DELAY time'''
        sleep_time = (MAIN_TICK_DELAY -(time.time()- cur_time))
#         if sleep_time < 0 :
#             log.critical("******* TIMING SKEWED(%f)******"%(sleep_time))
        sleep_time = 0 if sleep_time < 0 else sleep_time
        time.sleep(sleep_time)
    # end While(true)

g_screeners = []
g_ticker_stats = {}
def register_screeners(cfg):
    global g_screeners
    log.debug("registering screeners")
    g_screeners = Configure(cfg)

def update_data():
    #update stats only during ~12hrs, to cover pre,open,ah
    log.debug("updating data")
    sym_list = get_all_tickers()
    for scrn_obj in g_screeners:
        if scrn_obj.interval + scrn_obj.update_time < int(time.time()):
            s_list = sym_list.get(scrn_obj.ticker_kind)
            if not s_list :
                log.critical("unable to find ticker list kind %s"%(scrn_obj.ticker_kind))
                continue
            log.info ("updating screener data for %s num_sym: %d"%(scrn_obj.name, len(s_list)))                
            if scrn_obj.update(s_list, g_ticker_stats):
                scrn_obj.updated = True
                #update time. 
                # Sometimes, data not updated during market close etc. handle this in screener, update routine 
                scrn_obj.update_time = int(time.time())                 

def process_screeners ():
    log.debug("processing screeners")
    sym_list = get_all_tickers()    
    for scrn_obj in g_screeners:
        if scrn_obj.updated :
            s_list = sym_list.get(scrn_obj.ticker_kind)
            if not s_list :
                log.critical("unable to find ticker list kind %s"%(scrn_obj.ticker_kind))
                continue            
            log.info ("running screener - %s sym_num: %d"%(scrn_obj.name, len(s_list)))
            scrn_obj.screen(s_list, g_ticker_stats)
            scrn_obj.updated = False
            
def get_all_screener_data():
    #run thru all screeners and collect filtered data
    filtered_list = {}
    for scrn_obj in g_screeners:
        log.info("get screener data from %s"%(scrn_obj.name))
        filtered_list[scrn_obj.name] = scrn_obj.get_screened()
    return filtered_list

all_tickers = {"ALL":[], "MEGACAP":[], "GT50M": [], "LT50M": [], "OTC": [],
               "ALL500K":[], "MEGACAP500K":[], "GT50M500K": [], "LT50M500K": [], "OTC500K": [], "SPAC": []}
def get_all_tickers ():
    global ticker_import_time, all_tickers
    log.debug ("get all tickers")
    if ticker_import_time + 24*3600 < int(time.time()) :
        all_tickers = get_all_ticker_lists()
    return all_tickers
    
def get_screener_data():
#     log.info("msg %s"%(msg))
    data_set = get_all_screener_data()
    return data_set

def clean_states():
    ''' 
    clean states
    '''
    log.info("Clearing Db")

def load_config (cfg_file):
    global ScreenerConfig
    ScreenerConfig = readConf(cfg_file)
    
def arg_parse():
    '''
    arg parse
    '''
    parser = argparse.ArgumentParser(description='Wolfinch Screener')

    parser.add_argument('--version', action='version', version='%(prog)s 1.0.1')
    parser.add_argument("--clean",
                        help='Clean states,dbs and exit. Clear all the existing states',
                        action='store_true')
    parser.add_argument("--config", help='Wolfinch Screener config file')    
    parser.add_argument("--port", help='API Port')
    parser.add_argument("--restart", help='restart from the previous state', action='store_true')

    args = parser.parse_args()
    
    if args.config:
        log.debug("config file: %s" % (str(args.config)))
        if False == load_config(args.config):
            log.critical("Config parse error!!")
            parser.print_help()
            exit(1)
        else:
            log.debug("config loaded successfully!")
#             exit(0)
    else:
        parser.print_help()
        exit(1)    

    if args.clean:
        clean_states()
        exit(0)

    if args.port:
        log.debug("port: %s" % (str(args.port)))
        ui.port = args.port
    else:
        pass
#         parser.print_help()
#         exit(1)

    if args.restart:
        log.debug("restart enabled")
        print("Restarting from previous state")
    else:
        log.debug("restart disabled")

######### ******** MAIN ****** #########
if __name__ == '__main__':
    '''
    main entry point
    '''
    arg_parse()
    getcontext().prec = 8  # decimal precision
    print("Starting Wolfinch Screener..")
    try:
        screener_init()
        log.info("Starting Main forever loop")
        print("Starting Main forever loop")
        screener_main()
    except(KeyboardInterrupt, SystemExit):
        screener_end()
        sys.exit()
    except Exception as e:
        log.critical("Unexpected error: exception: %s" %(traceback.format_exc()))
        print("Unexpected error: exception: %s" %(traceback.format_exc()))
        screener_end()
        raise
#         traceback.print_exc()
#         os.abort()
    # '''Not supposed to reach here'''
    print("\nScreener end")

# EOF