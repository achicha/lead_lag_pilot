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
    """Lead lag startegy

    Parameters
    ----------


    """

    def __init__(self, *args, **kwargs):
        self.config = {}
        self.history = None
        self.working_memory = None
        self.kwargs = kwargs
        self.exchange = kwargs.get("exchange")
        self.feed = kwargs.get("feed")
        self.exchange.attach_feed(self.feed)
        self.size = kwargs.get("size", 0.001)
        self.config["size"] = self.size
        self.interval = kwargs.get("interval", "3m")
        self.symbol = kwargs.get("symbol", "BTCUSD")
        self.config["symbol"] = self.symbol
        self.config["interval"] = self.interval
        # self.time_rounder = RoundTime(interval=self.interval)
        self.persist = kwargs.get("persist", False)
        self.take_profit = kwargs.get("take_profit", 0.004)
        self.stop_loss = kwargs.get("stop_loss", 0.002)
        self.config["stop_loss"] = self.stop_loss
        # self.max_time_delta = kwargs.get("max_time_delta", timedelta(hours=36))

        self.max_history = kwargs.get(
            "max_history",
            200
        )

        self.filter_index = np.array([1])

        self.order_trackers = []
        self.short_stop_order = []
        self.long_stop_order = []

        # if self.kwargs.get("live", False):
        #     # Preload aggregator with history before reacting per bar.
        #     print("Is live! Preloading data")
        #     self.preload_data()
        #     asyncio.get_event_loop().create_task(self.send_ping())

        # self.aggregator.subscribe("bar_complete", self.on_bar)
        # self.feed.subscribe("trades", self.aggregator.update)

        self.performance_manager = MarginPerformance()
        self.performance_manager.attach_exchange(self.exchange)

        if self.persist:
            self.persistence = StrategyPersistence(
                db_string=kwargs.get("db_string")
            )
            self.strategy_id = self.persistence.create_strategy(
                strategy_name="strategy_1",
                start_date=datetime.utcnow(),
                attributes=self.config
            )
            self.exchange.subscribe("updates", self.persistence.store_updates)
            # self.candles.bar_subscribers.append(self.persistence.updates)

    @property
    def name(self):
        """Define the name of the strategy. Used to identify the strategy
        used by a trader"""
        return "lead_lag_pilot"

    def stop(self):
        logging.info("Stopping Exchange and Feed (stop method)")
        self.exchange.stop()
        self.feed.stop()

    def on_tick_lead(self, tick):
        pass
        # self.working_memory = pd.DataFrame(
        #     data=[bar.to_dict() for bar in self.aggregator.bars]
        # ).sort_values(by="mts").reset_index(drop=True) #.set_index("mts")

        # # self.working_memory["mts"] = self.working_memory.index
        # self.working_memory.loc[:, "datetime_index"] = self.working_memory["mts"].apply(
        #     lambda x: datetime.utcfromtimestamp(x/1000.)
        # )
        # self.working_memory.set_index("datetime_index", inplace=True)

        # # self.history = self.history[-self.config["max_history"]:]
        # self.indicators()
        # # if (self.feature_table.shape[0] > 0) and self.new_filtered_bar:
        # self.enter_long()
        # self.enter_short()

        # if not isinstance(self.history, pd.DataFrame):
        #     self.history = self.working_memory.copy()
        # else:
        #     self.history = pd.concat([
        #         self.history,
        #         self.working_memory.tail(1)
        #     ], sort=False)

        # if self.persist:
        #     self.persist_bar()


    def _align_table(self, table):
        table.reset_index(inplace=True)
        table.mts = table.mts.apply(
            self.time_rounder.round_milliseconds
        ).astype(np.int64)
        table.set_index("mts", inplace=True)
        return table

    def _add_profit_and_loss(self, history):
        orders = self.performance_manager.order_table()
        orders = self._align_table(orders)
        profit = self.performance_manager.profit_table()
        profit = self._align_table(profit)
        result = profit.combine_first(orders)
        result = pd.merge(
            history,
            result,
            left_index=True,
            right_index=True,
            how="left"
        )
        result["sum_profit"] = result["profit"].cumsum().fillna(method="ffill").fillna(value=0.0)
        result["sum_fees"] = result["fee"].cumsum().fillna(method="ffill").fillna(value=0.0)
        result["cumulative_pnl"] = result["sum_profit"] - result["sum_fees"]
        return result


    def _add_entry_points(self, history):
        history["long_price"] = history.apply(
            lambda x: x["price"] if x["order_size"] > 0.0 else None,
            axis=1
        )
        history["short_price"] = history.apply(
            lambda x: x["price"] if x["order_size"] < 0.0 else None,
            axis=1
        )
        return history

    def _performance(self):
        history = self.history.reset_index()
        history["mts"] = history["mts"].values.astype(np.int64) // 10 ** 6
        history.set_index("mts", inplace=True)
        results = self._add_profit_and_loss(history)
        results = self._add_entry_points(results)
        return results

    # def chart(self, path):
    #     """Helper for fetching the chart config related to a strategy"""
    #     results = self._performance()
    #     results.reset_index(inplace=True)
    #     del results["datetime"]
    #     chart(results, chart_config(self.config), path)

    def profit_table(self):
        orders_list = list(
            map(
                lambda x: (x.created_mts, x.execution_price, x.size),
                self.exchange.orders
            )
        )
        orders = pd.DataFrame(
            orders_list,
            columns=["executed_mts", "price", "size"]
        )
        orders["mts"] = orders["executed_mts"].apply(
            self.time_rounder.round_milliseconds
        ).astype(np.int64)
        orders = orders.apply(split_orders, axis=1)
        return orders

    ########################################################################
    # Long methods
    ########################################################################
    def enter_long(self):
        """Long entry """

        entry_conditions = all([
            # SAR crosses bellow close
            ch1["parabolic_sar"] < ch1["close"],
            ch2["parabolic_sar"] > ch2["close"],
            # SMA bellow close
            ch1["sma_60"] < ch1["low"],
        ])

        position = self.exchange.positions.get(self.symbol)
        max_position = self.kwargs.get("max_long_size", self.size * 5.0)
        if entry_conditions and (not position or position.size < max_position):
            logging.info("Entry long condition met!")
            if position:
                logging.info(position.size)
            sc.api_call(
              "chat.postMessage",
              channel="simple_scalper",
              text=f"\n----\nLong condition met. Id: {strategy.strategy_id} {datetime.now()}\n----\n"
            )
            # order_tracking_list = []
            if position and position.size < 0.0:
                try:
                    order_id = self.short_stop_order.pop(0)
                    self.exchange.cancel_order(order_id)
                except IndexError:
                    pass

            if position and (position.size >= 0.0):
                stop_loss_id = self.exchange.new_order(
                    "stop",
                    "BTCUSD",
                    float(ch1["close"])*(1.0-self.stop_loss),
                    -self.size,
                    margin=True
                )
                self.long_stop_order.append(stop_loss_id)

            order_id = self.exchange.new_order(
                "market",
                "BTCUSD",
                0.0,
                self.size,
                margin=True
            )


    ########################################################################
    # Short methods
    ########################################################################
    def enter_short(self):
        # """Short entry signal based on fast / slow MA"""
        # try:
        #     ch1 = self.working_memory.iloc[-1]
        #     ch2 = self.working_memory.iloc[-2]
        # except IndexError:
        #     return

        # entry_conditions = all([
        #     # SAR crosses bellow close
        #     ch1["parabolic_sar"] > ch1["close"],
        #     ch2["parabolic_sar"] < ch2["close"],
        #     # SMA bellow close
        #     ch1["sma_60"] > ch1["high"],
        # ])
        # position = self.exchange.positions.get(self.symbol)
        # max_position = -self.kwargs.get("max_short_size", self.size * 5.0)
        # if entry_conditions and (not position or position.size > max_position):
        #     logging.info("Entry short condition met!")
        #     if position:
        #         logging.info(position.size)
        #     sc.api_call(
        #       "chat.postMessage",
        #       channel="simple_scalper",
        #       text=f"\n----\nShort condition met. Id: {strategy.strategy_id} {datetime.now()}\n----\n"
        #     )
        #     # order_tracking_list = []
        #     # TODO: If already in a long position, try using limit order
        #     # Cancel limit order if not filled by next opertunity (both short/long)
        #     if position and position.size > 0.0:
        #         try:
        #             order_id = self.long_stop_order.pop(0)
        #             self.exchange.cancel_order(order_id)
        #         except IndexError:
        #             pass

        #     if position and (position.size <= 0.0):
        #         stop_loss_id = self.exchange.new_order(
        #             "stop",
        #             "BTCUSD",
        #             float(ch1["close"])*(1.0+self.stop_loss),
        #             self.size,
        #             margin=True
        #         )
        #         self.short_stop_order.append(stop_loss_id)

        #     order_id = self.exchange.new_order(
        #         "market",
        #         "BTCUSD",
        #         0.0,
        #         -self.size,
        #         margin=True
        #     )
