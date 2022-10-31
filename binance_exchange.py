from decimal import Decimal
import hashlib
import hmac
import re
import time
import urllib

import requests

from coin import Coin
from exchange import Exchange
import logman


class Binance(Exchange):
    def __init__(self, api_base, api_key, api_secret, live):
        self._api_base = api_base
        self._api_key = api_key
        self._api_secret = api_secret
        self.live = live

        self._session = requests.Session()
        self._test_connection()

    def _sign_query(self, query):
        """Signs the query for account end points."""
        m = hmac.new(
            self._api_secret.encode('utf-8'),
            query.encode('utf-8'),
            hashlib.sha256
        )
        return m.hexdigest()

    def _request(self, verb, target, signed=False, params=None):
        """Send request."""
        if self.live:
            logman.warn("WARNING LIVE")
        verbs = ['GET', 'POST', 'DELETE']
        if verb not in verbs:
            raise ValueError("Verb not supported")

        if params is None:
            params = {}

        headers = {}
        if signed:
            headers['X-MBX-APIKEY'] = self._api_key
            params['timestamp'] = int(time.time() * 1000)
            query = urllib.parse.urlencode(params)
            sig = self._sign_query(query)
            params['signature'] = sig

        query = urllib.parse.urlencode(params)
        if params:
            url = f'{self._api_base}{target}?{query}'
        else:
            url = f'{self._api_base}{target}'

        logman.info(f'{verb} "{url}"...')
        res = self._session.request(verb, url, headers=headers)
        logman.info(f'Status: {res.status_code}')
        if res.status_code != 200:
            logman.debug('Non 200 ------------')
            logman.debug(res.json())
            logman.debug(res.request.url)
            logman.debug(res.request.body)
            logman.debug(res.request.headers)
            logman.debug('--------------------')
        else:
            logman.debug(res.json())
        return res

    def _test_connection(self):
        res = self._request('GET', '/api/v3/ping')
        assert res.status_code == 200
        assert res.json() == {}

    def _get_exchange_info(self):
        res = self._request('GET', '/api/v3/exchangeInfo')
        assert res.status_code == 200
        return res.json()

    def _get_prices(self):
        res = self._request('GET', '/api/v3/ticker/price')
        assert res.status_code == 200
        return {p['symbol']: p['price'] for p in res.json()}

    def _get_account(self):
        res = self._request('GET', '/api/v3/account', signed=True)
        assert res.status_code == 200
        return res.json()

    def _get_book_ticker(self, symbol):
        params = {'symbol': symbol}
        res = self._request('GET', '/api/v3/ticker/bookTicker', params=params)
        assert res.status_code == 200
        return res.json()

    def setup_coins(self, main_asset, main_asset_count):
        """Setups the coin structure.

        Also checks that we have enough main_asset.

        Args:
            main_asset: string of the asset to buy coin with.
            main_asset_count: string of number of main_asset to use to buy coin.

        Returns:
            True if successful
        """
        Coin.main_asset = main_asset
        self.main_asset = main_asset
        self.main_asset_count = main_asset_count
        own = Decimal(self.get_balance(main_asset))
        logman.info(f'We have {own} {main_asset}')
        assert own >= Decimal(main_asset_count)

        exchange_info = self._get_exchange_info()
        prices = self._get_prices()

        for coin_data in exchange_info['symbols']:
            if coin_data['quoteAsset'] == main_asset:
                is_base_asset = main_asset == coin_data['quoteAsset']
                filters = coin_data['filters']
                lot_filter = next(f for f in filters if f['filterType'] == 'LOT_SIZE')
                price_filter = next(f for f in filters if f['filterType'] == 'PRICE_FILTER')
                symbol = coin_data['symbol']
                Coin(
                    name=coin_data['baseAsset'] if is_base_asset else coin_data['quoteAsset'],
                    symbol=symbol,
                    sell_side='sell' if is_base_asset else 'buy',
                    buy_side='buy' if is_base_asset else 'sell',
                    is_base_asset=is_base_asset,
                    qty_size=lot_filter['stepSize'],
                    price_size=price_filter['tickSize'],
                    min_qty=lot_filter['minQty'],
                    start_price=prices[symbol]
                )
        logman.info('Initialized Coins')
        return True

    def buy_coin(self, coin, quantity):
        """Market buys coin.

        Args:
            coin: a coin object.
            quantity: a string of the quantity to buy.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.123),...]
        """
        params = {
            'symbol': coin.symbol,
            'type': 'MARKET'
        }
        main_asset = coin.main_asset
        if coin.is_base_asset:
            logman.info(f'Buying {coin.symbol} with {quantity} {main_asset}')
            params['side'] = 'BUY'
            params['quoteOrderQty'] = quantity
            assert re.search(f'{main_asset}$', coin.symbol)
        else:
            logman.info(f'Selling {coin.symbol} with {quantity} {main_asset}')
            params['side'] = 'SELL'
            params['quantity'] = quantity
            assert re.search(f'^{main_asset}', coin.symbol)

        res = self._request('POST', '/api/v3/order', params=params, signed=True)
        assert res.status_code == 200

        fills = res.json()['fills']
        return [(fill['qty'], fill['price']) for fill in fills]

    def sell_coin(self, coin, quantity):
        """Market sells coin.

        Args:
            coin: a coin object.
            quantity: a string of the quantity to sell.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.456),...]
        """
        params = {
            'symbol': coin.symbol,
            'type': 'MARKET'
        }
        main_asset = coin.main_asset
        if coin.is_base_asset:
            logman.info(f'Selling {coin.symbol} with {quantity} not {main_asset}')
            params['side'] = 'SELL'
            params['quantity'] = quantity
            assert re.search(f'{main_asset}$', coin.symbol)
        else:
            logman.info(f'Buying {coin.symbol} with {quantity} not {main_asset}')
            params['side'] = 'BUY'
            params['quoteOrderQty'] = quantity
            assert re.search(f'^{main_asset}', coin.symbol)

        res = self._request('POST', '/api/v3/order', params=params, signed=True)
        assert res.status_code == 200

        fills = res.json()['fills']
        return [(fill['qty'], fill['price']) for fill in fills]

    def set_sell_limit(self, coin, quantity, price):
        """Sets sell limit for coin.

        Args:
            coin: a coin object.
            quantity: a decimal of the quantity to list.
            price: a decimal of the price to put the limit at.

        Returns:
            bool: whether successful or not
        """
        params = {
            'symbol': coin.symbol,
            'type': 'LIMIT',
            'timeInForce': 'GTC',
            'quantity': quantity,
            'price': price
        }
        main_asset = coin.main_asset
        if coin.is_base_asset:
            logman.info(f'Selling {coin.symbol} with {quantity} not {main_asset} @ {price}')
            params['side'] = 'SELL'
            assert re.search(f'{main_asset}$', coin.symbol)
        else:
            logman.info(f'Buying {coin.symbol} with {quantity} not {main_asset} @ {price}')
            params['side'] = 'BUY'
            assert re.search(f'^{main_asset}', coin.symbol)
        res = self._request('POST', '/api/v3/order', params=params, signed=True)

        return res

    def clear_all_orders(self, coin):
        """Clears all sell orders for coin.

        Args:
            coin: a coin object.

        Returns:
           the request response object
        """
        params = {'symbol': coin.symbol}
        res = self._request('DELETE', '/api/v3/openOrders', params=params, signed=True)
        return res

    def get_balance(self, name):
        """Gets current balance for named asset.

        Args:
            name: name of asset.

        Returns:
            decimal of the amount of coin.
        """
        account_data = self._get_account()
        if isinstance(name, Coin):
            name = name.name
        asset = next(c for c in account_data['balances'] if c['asset'] == name)
        return asset['free']

    def get_book_ticker(self, coin):
        """Gets the current ask and bid price of coin.

        Args:
            coin: a coin object.

        Returns:
            {
              'symbol': symbol,
              'ask_price': best ask price,
              'bid_price': best bid price
            }
        """
        book_top = self._get_book_ticker(coin.symbol)
        return {
            'symbol': coin.symbol,
            'ask_price': book_top['askPrice'],
            'bid_price': book_top['bidPrice']
        }
