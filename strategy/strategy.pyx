# pylint: disable=R0201
import os
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from cysignals.signals cimport sig_check
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

cdef class Strategy():
 
    cdef public object lag_exchange
    cdef public str lead_exchange_name
    cdef public str lag_exchange_name
    cdef public str time_diff
    cdef public long double target_percentage

    cdef public long double lead_price
    cdef public long double lag_price
    cdef public object lead_price_list
    cdef public object lag_price_list
    cdef public int order_id
    cdef public int stop_id
    cdef public list updates
    # cdef public object lead_dataframe

    def __init__(self, lead_exchange_name, lag_exchange, time_diff="10s", min_profit=0.0004):
        self.lag_exchange = lag_exchange
        self.lead_exchange_name = lead_exchange_name
        self.lag_exchange_name = lag_exchange.exchange
        self.time_diff = time_diff
        self.target_percentage = (self.lag_exchange.taker_fee * 2.0) +  min_profit
        
        self.lead_price = 0.0
        self.lag_price = 0.0
        self.lead_price_list = deque([], maxlen=500)
        self.lag_price_list = deque([], maxlen=500)
        self.order_id = 0
        self.stop_id = 0
        self.updates = []
        # self.lead_dataframe = None
        
    cpdef on_trade(self, dict trade):
        sig_check()
        if self.lead_exchange_name == trade["exchange"]:
            self.update_lead(trade)
        elif self.lag_exchange_name == trade["exchange"]:
            self.update_lag(trade)

    cpdef on_updates(self, dict message):
        self.updates.append(message)
        if message["message"] == "position_closed":
            self.lag_exchange.cancel_order(
                self.stop_id
            )
            self.lag_exchange.cancel_order(
                self.order_id
            )
        sig_check()

    cdef update_lead(self, dict trade):
        self.lead_price = trade["price"]
        self.lead_price_list.append(trade)
        if self.lag_price > 0.0:
            self.check_difference()
    
    cdef update_lag(self, dict trade):
        self.lag_price = trade["price"]
        self.lag_price_list.append(trade)
        # self.lag_dataframe = pd.DataFrame(
        #     self.lag_price_list
        # ).set_index("datetime", drop=True).last(self.time_diff)
        self.lag_exchange.datafeed(trade)

    cdef void create_position(self, long double target_price, long double stop_price, long double amount):
        self.lag_exchange.new_order(
            "market",
            "XBTUSD",
            0.0,
            amount,
            True
        )
        self.stop_id = self.lag_exchange.new_order(
            "stop",
            "XBTUSD",
            stop_price,
            -amount,
            True
        )
        self.order_id = self.lag_exchange.new_order(
            "limit",
            "XBTUSD",
            target_price,
            -amount,
            True
        )


    cdef void move_position(self, long double target_price, long double stop_price, long double amount):
        self.lag_exchange.update_order(
            self.stop_id,
            stop_price,
            -amount
        )
        self.lag_exchange.update_order(
            self.order_id,
            target_price,
            -amount
        )
        print(f"Updated order: {self.lag_exchange.orders[-1].price}" )
        
    cdef void close_position(self, long double size):
        self.lag_exchange.cancel_order(
            self.stop_id
        )
        self.lag_exchange.cancel_order(
            self.order_id
        )
        self.lag_exchange.new_order(
            "market",
            "XBTUSD",
            0.0,
            size,
            True
        )
        
    cdef void check_difference(self):
        cdef object lead_dataframe
        cdef long double min_price
        cdef long double max_price
        cdef long double trade_fee
        cdef long double target_price
        cdef long double stop_price
        cdef object positions
        lead_dataframe = pd.DataFrame(
            self.lead_price_list
        ).set_index("datetime", drop=True).last(self.time_diff)
        min_price = lead_dataframe.price.min()
        max_price = lead_dataframe.price.max()
        trade_fee = self.lag_price * (self.lag_exchange.taker_fee *2)
        positions = self.lag_exchange.positions
        if ((max_price - min_price) > trade_fee):
            min_pos = lead_dataframe.price.idxmin()
            max_pos = lead_dataframe.price.idxmax()
            if min_pos < max_pos:
                target_price = self.lag_price * (1.0 + self.target_percentage)
                stop_price = self.lag_price * (1.0 - (self.lag_exchange.taker_fee))
                if not positions:
                    print("Will Buy")
                    self.create_position(target_price, stop_price, 1.0)
                elif (positions["XBTUSD"].size > 0.0) and target_price > self.lag_exchange.orders[-1].price:
                    self.move_position(target_price, stop_price, 1.0)
                elif positions["XBTUSD"].size < 0.0:
                    self.close_position(-positions["XBTUSD"].size)
                    print("Closed old position.")
                    self.create_position(target_price, stop_price, 1.0)
            else:
                target_price = self.lag_price * (1.0 - self.target_percentage)
                stop_price = self.lag_price * (1.0 + (self.lag_exchange.taker_fee))
                if not positions:
                    print("Will Sell")
                    self.create_position(target_price, stop_price, -1.0)
                elif (positions["XBTUSD"].size < 0.0) and target_price < self.lag_exchange.orders[-1].price: # Add logic for only updating positive direction.
                    self.move_position(target_price, stop_price, -1.0)
                elif positions["XBTUSD"].size > 0.0:
                    self.close_position(-positions["XBTUSD"].size)
                    print("Closed old position.")
                    self.create_position(target_price, stop_price, -1.0)