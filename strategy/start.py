import numpy as np
from numpy_ringbuffer import RingBuffer
import pandas as pd
from collections import deque
from trader.exchanges import virtual
from .strategy import Strategy

if __name__ == "__main__":
    feed = virtual.Feed()
    lag_exchange = virtual.Exchange(
        exchange="kraken",
        taker_fee=0.0016,
        maker_fee=0.0004
    )
    lead_lag_strat = Strategy(
        lead_exchange_name="coinbasepro",
        lag_exchange=lag_exchange
    )
    feed.subscribe("trades", lead_lag_strat.on_trade)
    lag_exchange.attach_feed(feed)

    feed.start(
        exchanges=["coinbasepro", "kraken"],
        symbols=["BTCUSD", "XBTUSD"],
        from_date="2019-01-01 00:00:00",
        to_date="2019-02-01 00:01:00",
    )