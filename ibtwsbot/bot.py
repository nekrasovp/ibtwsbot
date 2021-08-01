#!/usr/bin/env python
# encoding: utf-8

import math
from time import time
from random import randrange, seed
from xml.etree import ElementTree
from logging import Logger

import numpy as np
from pandas import DataFrame, Series, Timestamp, Timedelta

from ib_insync import IB, util, Position, PnLSingle, \
    Contract, ScannerSubscription, TagValue, Stock, \
    LimitOrder, MarketOrder, BracketOrder, \
    OrderStatus, Order, Forex, PortfolioItem


class Tbot():
    """
    Init and run main loop
    """

    def __init__(self, log: Logger, script, tws, db):
        """
        Init counter and enable logging.
        If the connection to TWS succeeded, then ib will be synchronized with TWS/IBG.
        The current state is now available via methods such as ib.positions(), ib.trades(),
        ib.openTrades(), ib.accountValues() or ib.tickers()
        """
        self.logger = log
        self.last_fetch_time = int(time())
        self.unrealizedPNLmax = script.unrealizedpnlmax
        self.dry_run = script.dry_run
        self.loop_interval = script.loop_interval
        if self.dry_run:
            self.logger.info("Initializing dry run. Orders printed below represent what would be "
                         "posted.")
        else:
            self.logger.info("Runner initializing, connecting to the API. Live run: executing real "
                         "trades.")
        # Initialise exchanges
        self.data_provider_list = []
        self.ib = IB()
        self.logger.info("Connecting to TWS API.")
        self.ib.connect(tws.ip, tws.port, clientId=tws.clientid)
        while not self.ib.isConnected():
            pass
        self.data_provider_list.append(self.ib)
        # Load scanners params and write in to file
        self.logger.info("Loading scanners parameters.")
        self.scanner_params_xml = ElementTree.fromstring(self.ib.reqScannerParameters())
        with open("scanner_params.xml", "w") as _:
            _.write(self.ib.reqScannerParameters())
        # Parse scanner params xml
        self.scanner_params = dict()
        self.parse_scanner_params()
        self.scanDataContracts = []
        # Load account values
        self.accountValues = util.df(self.ib.accountValues())
        if not self.accountValues.empty:
            self.logger.info('Loading account values')
        self.accountValues = self.get_account_values()
        # Load portfolio
        self.logger.info("Loading portfolio.")
        self.portfolio = []
        self.portfolio = self.ib.portfolio()
        if self.portfolio:
            for _ in self.portfolio:
                self.logger.info(_)
        # Load positions
        self.logger.info("Loading positions.")
        self.positions = self.ib.positions()
        if self.positions:
            for _ in self.positions:
                self.logger.info(_)
        # Load orders
        self.logger.info("Loading trades and orders.")
        self.trades = []
        self.trades = self.ib.trades()
        self.openOrders = []
        self.openOrders = self.ib.openOrders()
        if len(self.openOrders):
            for _ in self.openOrders:
                self.logger.info(f"Open OrderId={_.orderId}")
        # Containers init
        self.quote_collector = []
        self.run_step = 0

    def disconnect(self):
        self.ib.disconnect()
        self.logger.info("Shutdown application")
        # self.order_history_to_pickle(self.cache_path) # TODO pickle state

    # region Account
    def get_account_values(self):
        # Get available currency list filtered for empty value
        ls = [x for x in set(self.accountValues.currency) if x]
        # Print available currency non empty values
        acc = {}
        for c in ls:
            mask = (self.accountValues.value != '0.00') & \
                   (self.accountValues.account != self.accountValues.value) & \
                   (self.accountValues.currency == str(c))
            acc[c] = self.accountValues[mask]
        self.logger.info(f"Account base currencies: {ls}")
        return acc
    # endregion

    # region Scanner
    def scanner_subscription(self):
        """
        Scan for stock with scanner
        """
        sub = ScannerSubscription(
            instrument='STK',
            locationCode='STK.US.MAJOR',
            scanCode='HOT_BY_VOLUME')

        tag_values = [
            TagValue("changePercAbove", "10"),
            TagValue('priceAbove', '10'),
            TagValue('priceBelow', '50')]

        self.logger.info(f'ScannerSubscription(instrument={sub.instrument} '
                         f'locationCode={sub.locationCode} scanCode={sub.scanCode}')

        if isinstance(tag_values, list):
            for _ in tag_values:
                self.logger.info(_)
        # the tagValues are given as 3rd argument; the 2nd argument must always be an empty
        # list (IB has not documented the 2nd argument and it's not clear what it does)
        scan_data = self.ib.reqScannerData(sub, [], tag_values)
        self.logger.info(f'Scanner return {len(scan_data)} contracts')
        return [sd.contractDetails.contract for sd in scan_data]

    def parse_scanner_params(self):
        """Fill scanner_params dict with parsed scanner_params_xml"""
        # find all tags that are available for filtering
        _ = [elem.text for elem in self.scanner_params_xml.findall(
            './/AbstractField/code')]
        self.logger.info(f'{len(_)} tags found.')
        self.scanner_params['Tags'] = _
        # find locations available
        _ = [e.text for e in self.scanner_params_xml.findall(
            './/locationCode')]
        self.logger.info(f'{len(_)} locations found.')
        self.scanner_params['LocationCodes'] = _
        # find instrument types
        _ = set(e.text for e in self.scanner_params_xml.findall(
            './/Instrument/type'))
        self.logger.info(f'{len(_)} instrument types found.')
        self.scanner_params['InstrumentTypes'] = _
        # find scan codes
        _ = [e.text for e in self.scanner_params_xml.findall(
            './/scanCode')]
        self.logger.info(f'{len(_)} scan codes found.')
    # endregion

    # region Stocks
    def _bars_for_contract(self, contract: Contract):
        """
        Fully qualify the given contracts in-place.
        Get the datetime of earliest available historical data
        for the contract.
        Request historical bar data.
        :param contract: IB Contract
        """
        # contract = Contract(symbol=contract.symbol, exchange=contract.exchange,
        #                     currency=contract.currency, localSymbol=contract.localSymbol,
        #                     tradingClass=contract.tradingClass, secType=contract.secType)
        contract = self.ib.qualifyContracts(contract)[0]
        # self.logger.info(f'Contract qualified: {contract}')
        # headTimeStamp = self.ib.reqHeadTimeStamp(contract, whatToShow='Trades', useRTH=True)
        # self.logger.info(f'Datetime of earliest available historical data: {headTimeStamp}')
        try:
            return self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='7 D',
                barSizeSetting='5 mins',
                whatToShow='MIDPOINT',
                useRTH=True)
        except Exception as e:
            self.logger.error(e.__doc__)
            return []

    def _process_term_for_new_contract(self, contract: Contract):
        """
        Fetch bars and process terms for new contract.
        :param contract: IB Contract
        :return:
        """
        bars_df = util.df(self._bars_for_contract(contract))
        # bars_df = self.set_technical_indicators(bars_df)
        if not isinstance(bars_df, DataFrame):
            self.logger.info(f"Data error with {contract}")
            return None
        foul_time_m = Timedelta(Timestamp('now') - bars_df['date'].values[-1]).seconds / 60.0
        # Check mins between now and last fetched bar
        if foul_time_m > 10000:
            self.logger.info("Data is outdated")
        self.logger.info(f"Processing terms for {contract}")
        price_stat = {'mean':bars_df[-50:-1]['close'].mean(),
                 'std':bars_df[-50:-1]['close'].std(),
                 'min':bars_df[-50:-1]['close'].min(),
                 'max':bars_df[-50:-1]['close'].max(),
                 'last':bars_df.iloc[-1]['close']}
        self.logger.info(price_stat)
        if bars_df.iloc[-1].low > bars_df.iloc[-2].high and \
                bars_df.iloc[-1].close > bars_df.iloc[-2].close and \
                0 < bars_df.iloc[-1]['volume'] < bars_df[-50:-1]['volume'].mean() * 1.5:
                # Get max price between days
                maxPrice = bars_df['high'].max()
                # Place Bracket order
                o = IB.bracketOrder(self.ib,
                                    action="BUY",
                                    quantity=1,
                                    limitPrice=maxPrice,
                                    takeProfitPrice=maxPrice*1.05,
                                    stopLossPrice=maxPrice*0.95)
                self.logger.info(f"Append {o} for {contract} to quote collector")
                self.quote_collector.append((contract, o))

    @staticmethod
    def set_technical_indicators(dataset: DataFrame):
        """
        Manipulate DataFrame in any manners
        :param dataset:
        :return:
        """
        # Create 7 and 21 ticks Moving Average
        dataset['ma7'] = dataset['close'].rolling(window=7).mean()
        dataset['ma21'] = dataset['close'].rolling(window=21).mean()
        # Create MACD
        dataset['26ema'] = dataset['close'].ewm(span=26).mean()
        dataset['12ema'] = dataset['close'].ewm(span=12).mean()
        dataset['MACD'] = (dataset['12ema'] - dataset['26ema'])
        # Create Bollinger Bands
        dataset['20sd'] = dataset['close'].rolling(20).std()
        dataset['upper_band'] = dataset['ma21'] + (dataset['20sd'] * 2)
        dataset['lower_band'] = dataset['ma21'] - (dataset['20sd'] * 2)
        # Create Exponential moving average
        dataset['ema'] = dataset['close'].ewm(com=0.5).mean()
        return dataset.dropna()
    # endregion

    # region Portfolio
    def _process_portfolioitems(self):
        self.logger.info("Fetching positions")
        self.portfolio = self.ib.portfolio()
        self.ib.sleep(1)
        for p in self.portfolio:
            self.logger.info(f"Process term for {p}")
            self._process_term_for_portfolioitem(p)

    def _process_term_for_portfolioitem(self, p: PortfolioItem):

        if not isinstance(p, PortfolioItem):
            self.logger.error("Missed portfolio item")
            return
        if p.position > 0:
            is_long = True
        elif p.position == 0:
            self.logger.info("Position is empty, something goes wrong")
            return
        else:
            is_long = False

        unrealizedPNLpercent = 100*p.unrealizedPNL/p.averageCost

        if unrealizedPNLpercent < self.unrealizedPNLmax:
            if is_long:
                o = MarketOrder(action="SELL", totalQuantity=p.position)
            else:
                o = MarketOrder(action="BUY", totalQuantity=p.position)
            self.quote_collector.append((p.contract, o))
    # endregion

    #region Orders
    def _canceling_openOrders(self):
        for o in self.openOrders:
            self.logger.info(f"Canceling order {o.orderId}")
            self.ib.cancelOrder(o)
            self.ib.sleep(1)

    def process_trades(self):
        self.logger.info("Fetching trades")
        self.trades = self.ib.trades()
        for t in self.trades:
            if t.orderStatus.status not in OrderStatus.DoneStates:
                self.logger.info(f"Process terms for "
                                 f"{t.order.action} "
                                 f"{t.contract.symbol}"
                                 f"@{t.order.lmtPrice}")
                self._process_term_for_exist_orders(t.contract, t.order)

    def _process_term_for_exist_orders(self, contract: Contract, order: Order):
        bars_df = util.df(self._bars_for_contract(contract))
        bars_df = self.set_technical_indicators(bars_df)
        if not isinstance(bars_df, DataFrame):
            self.logger.info(f"Data error for {contract}")
            return None
        foul_time_m = Timedelta(Timestamp('now') - bars_df['date'].values[-1]).seconds / 60.0
        # Check min's between now and last fetched bar
        # Reduce to nearly zero to fetch only working markets
        if foul_time_m > 10000:
            self.logger.info("Data is outdated")

        if bars_df.iloc[-1].close > (bars_df.iloc[-1].high * 0.95) or bars_df.iloc[-1].close > (
                bars_df.iloc[-1].high * 0.95):
            self.ib.cancelOrder(order)

    #endregion

    # region Helpers
    def proceed_quote_collector(self):
        self.logger.info(f"Proceed {len(self.quote_collector)} orders")
        for q in self.quote_collector[:]:
            contract, order = q
            self.logger.info(f"Contract: {contract}")
            self.logger.info(f"Order: {order}")
            self.logger.info(f"Placing order")
            if not self.dry_run:
                trade = self.ib.placeOrder(contract, order)
                self.ib.sleep(1)
                self.logger.info(f"\n{util.df(trade.log)}")
            self.quote_collector.remove(q)

    def _wait_timeout(self) -> bool:
        """
        Check if reload timeout passed, use loop_interval from settings
        Use random generator and random seed equal time
        Bypass on 1 run
        :return : True if timeout passed, False otherwise
        :rtype: bool
        """
        now_time = int(time() - 1)
        passed_time = now_time - self.last_fetch_time
        seed(now_time)
        rand_interval = randrange(self.loop_interval-5, self.loop_interval+5)
        if (passed_time > rand_interval) or self.run_step == 0:
            self.last_fetch_time = now_time
            return True
        else:
            return False

    @staticmethod
    def rounded_to_precision(number: float, precision: int = 0) -> float:
        """
        Given a number, round it to the nearest tick. Very useful for sussing float error
        out of numbers: e.g. rounded_to_precision(401.46, 2) -> 401.46, whereas processing is
        normally with floats would give you 401.46000000000004.
        Use this after adding/subtracting/multiplying numbers.
        """
        if precision > 0:
            decimal_precision = math.pow(10, precision)
            return math.trunc(number * decimal_precision) / decimal_precision
        else:
            return float(('%d'.format(number)))

    # endregion

    # region Main Loop
    def run_bot(self):
        while True:
            if self._wait_timeout():
                # Check trades
                if len(self.trades): self.process_trades()
                # Check positions in portfolio
                if len(self.portfolio): self._process_portfolioitems()
                portfolio_contracts = [i.contract for i in self.portfolio]
                # Scan for stock in scanner and process terms for fresh contracts
                # self.scanDataContracts = self.scanner_subscription()
                # if self.scanDataContracts:
                #     self.logger.info(f"Checking terms for {len(self.scanDataContracts)} contracts...")
                #     for c in self.scanDataContracts:
                #         if c not in portfolio_contracts:
                #             self._process_term_for_new_contract(c)
                # Process contracts from list
                contracts = self.ib.qualifyContracts(Forex('EURUSD'), Forex('USDJPY'),
                                                     Forex('GBPUSD'), Forex('USDCHF'),
                                                     Forex('EURCHF'))
                for c in contracts:
                    if c not in portfolio_contracts:
                        self._process_term_for_new_contract(c)

            # Place an orders and clear quote collector on return
            if len(self.quote_collector) != 0:
                self.proceed_quote_collector()

            self.run_step += 1


    # endregion



