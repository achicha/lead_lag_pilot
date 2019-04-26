import json
from trader.exchanges import virtual
from strategy import Strategy


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
    lag_exchange.subscribe("updates", lead_lag_strat.on_updates)
    # lag_exchange.attach_feed(feed)
    print("Starting feed!")
    feed.start(
        exchanges=["coinbasepro", "kraken"],
        symbols=["BTCUSD", "XBTUSD"],
        from_date="2019-01-01 00:00:00",
        to_date="2019-01-10 00:00:00",
    )
    print("Done with feed")
    print(lag_exchange.wallets)
    with open("results/results.json", "w") as file:
        json.dump(lead_lag_strat.updates, file)
