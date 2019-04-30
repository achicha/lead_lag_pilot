import json
from datetime import datetime
from trader.exchanges import virtual
from strategy import Strategy

def run_simulation(lead_exchange_name, lag_exchange_name, lead_symbol, lag_symbol, taker_fee, maker_fee,
                   from_date, to_date, time_diff, min_profit):
    feed = virtual.Feed()
    lag_exchange = virtual.Exchange(
        exchange=lag_exchange_name,
        taker_fee=taker_fee,
        maker_fee=maker_fee
    )
    lead_lag_strat = Strategy(
        lead_exchange_name=lead_exchange_name,
        lag_exchange=lag_exchange,
        lag_symbol=lag_symbol,
        time_diff=time_diff,
        min_profit=min_profit
    )
    feed.subscribe("trades", lead_lag_strat.on_trade)
    lag_exchange.subscribe("updates", lead_lag_strat.on_updates)
    # lag_exchange.attach_feed(feed)
    print("Starting feed!")
    feed.start(
        exchanges=[lead_exchange_name, lag_exchange_name],
        symbols=[lead_symbol, lag_symbol],
        from_date=from_date,
        to_date=to_date
    )
    print("Done with feed")
    print(lag_exchange.wallets)
    datenow = datetime.now().isoformat()
    with open(f"results/results_{datenow}.json", "w") as file:
        json.dump(lead_lag_strat.updates, file)

if __name__ == "__main__":
    run_simulation(
        lead_exchange_name="binance",
        lead_symbol="BTCUSDT",
        lag_exchange_name="kraken",
        lag_symbol="XBTUSD",
        taker_fee=0.0014,
        maker_fee=0.0004,
        from_date="2019-02-01 00:00:00",
        to_date="2019-02-10 00:00:00",
        time_diff="10s",
        min_profit=0.0004
    )
