# pylint: disable=R0201
import os
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque
# from libcpp.collections cimport deque
# from trader import indicators
from trader.exchanges import virtual
# from trader.tools.time_tools import RoundTime
# from trader.bars import DollarBars, VolumeBars, CandleBars
from trader.managers import MarginPerformance, StrategyPersistence
# import joblib
# from amplify_charts import chart
# from strategy.utils.tools import get_trade_events

class Strategy():

    def __init__(self, lead_exchange_name, lag_exchange, time_diff="6s", lag_symbol="BTCUSD"):
        self.lag_exchange = lag_exchange
        self.lead_exchange_name = lead_exchange_name
        self.lag_exchange_name = lag_exchange.exchange
        self.time_diff = time_diff
        self.lag_symbol = lag_symbol

        self.lead_price = 0.0
        self.lag_price = 0.0
        self.lead_price_list = deque([], maxlen=500)
        self.lag_price_list = deque([], maxlen=500)
        self.order_id = 0
        self.stop_id = 0
        self.updates = []
        # self.lead_dataframe = None

    def on_trade(self, trade):
        if self.lead_exchange_name == trade["exchange"]:
            self.update_lead(trade)
        elif self.lag_exchange_name == trade["exchange"]:
            self.update_lag(trade)

    def on_updates(self, message):
        self.updates.append(message)

    def update_lead(self, trade):
        self.lead_price = trade["price"]
        self.lead_price_list.append(trade)
        if self.lag_price > 0.0:
            self.check_difference()

    def update_lag(self, trade):
        self.lag_price = trade["price"]
        self.lag_price_list.append(trade)
        # self.lag_dataframe = pd.DataFrame(
        #     self.lag_price_list
        # ).set_index("datetime", drop=True).last(self.time_diff)
        self.lag_exchange.datafeed(trade)
        positions = self.lag_exchange.positions
        if positions:
            self.close_position(-positions[self.lag_symbol].size)

    def create_position(self, amount):
        self.lag_exchange.new_order(
            "market",
            self.lag_symbol,
            0.0,
            amount,
            True
        )

    def close_position(self, size):
        self.lag_exchange.new_order(
            "market",
            self.lag_symbol,
            0.0,
            size,
            True
        )

    def check_difference(self):
        lead_dataframe = pd.DataFrame(
            self.lead_price_list
        ).set_index("datetime", drop=True).last(self.time_diff)
        min_price = lead_dataframe.price.min()
        max_price = lead_dataframe.price.max()
        positions = self.lag_exchange.positions
        min_pos = lead_dataframe.price.idxmin()
        max_pos = lead_dataframe.price.idxmax()
        if min_pos < max_pos:
            if not positions:
                print("Will Buy")
                self.create_position(1.0)
        else:
            if not positions:
                print("Will Sell")
                self.create_position(-1.0)
