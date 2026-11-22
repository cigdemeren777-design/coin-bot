#!/usr/bin/env python3
"""Hourly, read-only Binance spot market watcher and paper-trade simulator.
No exchange keys, no real orders, no leverage. Python standard library only.
"""
import json, os, urllib.request, datetime, pathlib, math
ROOT=pathlib.Path(__file__).resolve().parent
STATE=ROOT/"panel"/"bot_state.json"
SYMBOLS=("BTCUSDT","ETHUSDT")
def candles(symbol):
    url="https://api.binance.com/api/v3/klines?symbol="+symbol+"&interval=1h&limit=210"
    req=urllib.request.Request(url,headers={"User-Agent":"CoinPaperBot/1.0"})
    with urllib.request.urlopen(req,timeout=20) as resp: data=json.load(resp)
    now=int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
    closed=[x for x in data if int(x[6])<now]
    if len(closed)<201: raise ValueError("Insufficient closed candles")
    for a,b in zip(closed,closed[1:]):
        if int(b[0])-int(a[0])!=3600000:raise ValueError("Candle gap")
    return closed
def ema(prices,period):
    alpha=2/(period+1);value=prices[0]
    for price in prices[1:]:value=alpha*price+(1-alpha)*value
    return value
def run():
    state={"version":1,"updated_at":None,"mode":"paper","cash_usdt":1000.0,"positions":{},"history":[],"signals":{}}
    if STATE.exists():
        loaded=json.loads(STATE.read_text(encoding="utf-8"))
        if loaded.get("mode")!="paper":raise ValueError("Unexpected mode")
        state.update(loaded)
    state["positions"]=state.get("positions") or {}
    state["history"]=state.get("history") or []
    state["signals"]=state.get("signals") or {}
    for symbol in SYMBOLS:
        data=candles(symbol)
        prices=[float(x[4]) for x in data]
        last=prices[-1]
        e50=ema(prices,50);e200=ema(prices,200)
        signal="BUY" if e50>e200 else "EXIT"
        candle_time=int(data[-1][0])
        previous=state["signals"].get(symbol,{})
        if previous.get("candle_time")==candle_time:continue
        state["signals"][symbol]={"signal":signal,"candle_time":candle_time,"price":last,"ema50":round(e50,4),"ema200":round(e200,4)}
        position=state["positions"].get(symbol)
        fee=.001;slippage=.0005
        if signal=="BUY" and position is None and len(state["positions"])<2 and state["cash_usdt"]>=100:
            stake=100.0
            qty=(stake*(1-fee))/(last*(1+slippage))
            state["cash_usdt"]-=stake
            state["positions"][symbol]={"qty":qty,"entry_price":last,"stake":stake,"opened_at":candle_time}
            state["history"].append({"symbol":symbol,"action":"PAPER_BUY","price":last,"time":candle_time,"stake":stake})
        elif signal=="EXIT" and position is not None:
            proceeds=position["qty"]*last*(1-slippage)*(1-fee)
            state["cash_usdt"]+=proceeds
            state["history"].append({"symbol":symbol,"action":"PAPER_SELL","price":last,"time":candle_time,"proceeds":round(proceeds,4),"pnl":round(proceeds-position["stake"],4)})
            del state["positions"][symbol]
    state["updated_at"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["cash_usdt"]=round(state["cash_usdt"],6)
    state["history"]=state["history"][-100:]
    STATE.parent.mkdir(parents=True,exist_ok=True)
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Updated paper bot state:",state["updated_at"])
if __name__=="__main__":run()
