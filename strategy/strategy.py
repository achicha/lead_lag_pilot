# pylint: disable=R0201
import os
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque
# from trader import indicators
from trader.exchanges import virtual
# from trader.tools.time_tools import RoundTime
# from trader.bars import DollarBars, VolumeBars, CandleBars
from trader.managers import MarginPerformance, StrategyPersistence
# import joblib
# from amplify_charts import chart
# from strategy.utils.tools import get_trade_events


class Strategy():
    
    def __init__(self, lead_exchange_name, lag_exchange, time_diff="10s"):
        self.lag_exchange = lag_exchange
        self.lead_exchange_name = lead_exchange_name
        self.lag_exchange_name = lag_exchange.exchange
        self.time_diff = time_diff
        self.trade_locked = False
        
        self.lead_price = None
        self.lag_price = None
        self.last_lag_trade = None
        self.lead_price_list = deque(maxlen=500)
        self.lag_price_list = deque(maxlen=500)
        
    def on_trade(self, trade):
        if self.lead_exchange_name == trade["exchange"]:
            self.update_lead(trade)
        elif self.lag_exchange_name == trade["exchange"]:
            self.update_lag(trade)

    def update_lead(self, trade):
        self.lead_price = trade["price"]
        self.lead_price_list.append(trade)
        self.lead_dataframe = pd.DataFrame(
            self.lead_price_list
        ).set_index("datetime", drop=True).last(self.time_diff)
        min_price = self.lead_dataframe.price.min()
        max_price = self.lead_dataframe.price.max()
        trade_fee = trade["price"] * (self.lag_exchange.taker_fee *2)
        # this should be moved down to seperate function
        if (max_price - min_price) > trade_fee:
            min_pos = self.lead_dataframe.price.idxmin()
            max_pos = self.lead_dataframe.price.idxmax()
            if not self.trade_locked:
                if min_pos < max_pos:
                    target_price = self.lag_price * (1.0 + self.lag_exchange.taker_fee *2)
                    print("Will Buy")
                    self.lag_exchange.new_order(
                        "market",
                        "XBTUSD",
                        0.0,
                        1.0,
                        True
                    )
                    self.lag_exchange.new_order(
                        "limit",
                        "XBTUSD",
                        target_price,
                        -1.0,
                        True
                    )
                else:
                    target_price = self.lag_price * (1.0 - self.lag_exchange.taker_fee *2)
                    print("Will Sell")
                    self.lag_exchange.new_order(
                        "market",
                        "XBTUSD",
                        0.0,
                        -1.0,
                        True
                    )
                    self.lag_exchange.new_order(
                        "limit",
                        "XBTUSD",
                        target_price,
                        1.0,
                        True
                    )
                self.trade_locked = True
        else:
            if self.trade_locked:
                print("will reset")
            self.trade_locked = False
            
#         print(f"lead: {self.lead_price}")
    
    def update_lag(self, trade):
        self.lag_price = trade["price"]
        self.lag_price_list.append(trade)
        self.lag_dataframe = pd.DataFrame(
            self.lag_price_list
        ).set_index("datetime", drop=True).last(self.time_diff)
        
    def check_difference(self):
        pass