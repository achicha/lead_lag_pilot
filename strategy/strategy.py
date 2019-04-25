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
    
    def __init__(self, lead_exchange_name, lag_exchange, time_diff="10s", min_profit=0.0004):
        self.lag_exchange = lag_exchange
        self.lead_exchange_name = lead_exchange_name
        self.lag_exchange_name = lag_exchange.exchange
        self.time_diff = time_diff
        self.target_percentage = (self.lag_exchange.taker_fee * 2.0) +  min_profit
        
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
        if self.lag_price:
            self.check_difference()
    
    def update_lag(self, trade):
        self.lag_price = trade["price"]
        self.lag_price_list.append(trade)
        self.lag_dataframe = pd.DataFrame(
            self.lag_price_list
        ).set_index("datetime", drop=True).last(self.time_diff)
        self.lag_exchange.datafeed(trade)

    def create_position(self, target_price, amount):
        self.lag_exchange.new_order(
            "market",
            "XBTUSD",
            0.0,
            amount,
            True
        )
        self.order_id = self.lag_exchange.new_order(
            "limit",
            "XBTUSD",
            target_price,
            -amount,
            True
        )

    def move_position(self, target_price, amount):
        self.lag_exchange.update_order(
            self.order_id,
            target_price,
            -amount
        )
        print(f"Updated order: {self.lag_exchange.orders[-1].price}" )
        
    def close_position(self, size):
        self.lag_exchange.new_order(
            "market",
            "XBTUSD",
            0.0,
            size,
            True
        )
        self.lag_exchange.cancel_order(
            self.order_id
        )
        
    def check_difference(self):
        min_price = self.lead_dataframe.price.min()
        max_price = self.lead_dataframe.price.max()
        trade_fee = self.lag_price * (self.lag_exchange.taker_fee *2)
        positions = self.lag_exchange.positions
        if ((max_price - min_price) > trade_fee):
            min_pos = self.lead_dataframe.price.idxmin()
            max_pos = self.lead_dataframe.price.idxmax()
            if min_pos < max_pos:
                target_price = self.lag_price * (1.0 + self.target_percentage)
                if not positions:
                    print("Will Buy")
                    self.create_position(target_price, 1.0)
                elif (positions["XBTUSD"].size > 0.0) and target_price > self.lag_exchange.orders[-1].price:
                    self.move_position(target_price, 1.0)
                elif positions["XBTUSD"].size < 0.0:
                    self.close_position(-positions["XBTUSD"].size)
                    print("Closed old position. Will Buy")
                    self.create_position(target_price, 1.0)
            else:
                target_price = self.lag_price * (1.0 - self.target_percentage)
                if not positions:
                    print("Will Sell")
                    self.create_position(target_price, -1.0)
                elif (positions["XBTUSD"].size < 0.0) and target_price < self.lag_exchange.orders[-1].price: # Add logic for only updating positive direction.
                    self.move_position(target_price, -1.0)
                elif positions["XBTUSD"].size > 0.0:
                    self.close_position(-positions["XBTUSD"].size)
                    print("Closed old position. Will Sell")
                    self.create_position(target_price, -1.0)