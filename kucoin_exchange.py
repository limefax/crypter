import base64
from decimal import Decimal
import json
import hashlib
import hmac
import time
import urllib
import uuid

import requests

from coin import Coin
from exchange import Exchange


class Kucoin(Exchange):
    def __init__(self, api_base, api_key, api_secret, api_passphrase, live):
        self._session = requests.Session()
        self._api_base = api_base
        self._api_key = api_key
        self._api_secret = api_secret
        self._api_passphrase = api_passphrase
        self.live = live

        self._passphrase = base64.b64encode(hmac.new(
            self._api_secret.encode('utf-8'),
            self._api_passphrase.encode('utf-8'),
            hashlib.sha256
        ).digest())

        # test everything is online and accessible
        self._check_alive()
        self._check_auth()

    def _sign_request(self, verb, target, params):
        """Returns updated headers."""
        now = str(int(time.time() * 1000))
        body = json.dumps(params) if params else ''
        sign_str = f'{now}{verb}{target}{body}'
        signature = base64.b64encode(hmac.new(
            self._api_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).digest())

        headers = {
            'KC-API-KEY': self._api_key,
            'KC-API-SIGN': signature,
            'KC-API-TIMESTAMP': now,
            'KC-API-PASSPHRASE': self._passphrase,
            'KC-API-KEY-VERSION': '2'  # TODO
        }

        return headers

    def _request(self, verb, target, params=None, signed=False):
        """Send request."""
        if self.live:
            print("WARNING LIVE")
        verbs = ['GET', 'POST', 'DELETE']
        url_verbs = ['GET', 'DELETE']
        body_verbs = ['POST']

        if verb not in verbs:
            raise ValueError("Verb not supported")

        if params is None:
            params = {}

        # build url
        if params and verb in url_verbs:
            query = urllib.parse.urlencode(params)
            url = f'{self._api_base}{target}?{query}'
            target = f'{target}?{query}'
        else:
            url = f'{self._api_base}{target}'

        headers = {}
        # deal with signing
        if signed:
            if verb in body_verbs:
                headers.update(self._sign_request(verb, target, params))
            else:
                headers.update(self._sign_request(verb, target, None))

        print(f'{verb} "{url}"...')
        # decide where to put params
        if verb in url_verbs:
            res = self._session.request(verb, url, headers=headers)
        elif verb in body_verbs:
            body = json.dumps(params)
            print(body)
            headers['Content-Type'] = 'application/json'
            res = self._session.request(verb, url, data=body, headers=headers)
        else:
            raise ValueError('Verb not found')

        print(f'Status: {res.status_code}')
        if res.status_code != 200:
            print('Non 200 ------------')
            print(res.json())
            print(res.request.url)
            print(res.request.body)
            print(res.request.headers)
            print('--------------------')
        else:
            print(res.json())
        return res

    def _check_alive(self):
        """Check we can get timestamp."""
        res = self._request('GET', '/api/v1/timestamp')
        assert res.status_code == 200
        data = res.json()
        assert data['code'] == '200000'
        print(f'Exchange is alive\nCurrent Time: {data["data"]}\n')

    def _check_auth(self):
        """Check we can get user info."""
        res = self._request('GET', '/api/v1/sub/user', signed=True)
        assert res.status_code == 200
        print('Auth works\n')

    def _get_market(self, market=None):
        """Gets all symbols in market."""
        params = {'market': market} if market is not None else None
        return self._request('GET', '/api/v1/symbols', params=params)

    def _get_price(self, symbol):
        """Get ticker for symbol."""
        params = {'symbol': symbol}
        return self._request('GET', '/api/v1/market/orderbook/level1', params=params)

    def _get_all_tickers(self):
        """Get all tickers."""
        return self._request('GET', '/api/v1/market/allTickers')

    def _query_order(self, order_id):
        """Query order status from order id."""
        return self._request('GET', f'/api/v1/orders/{order_id}', signed=True)

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
        assert own > main_asset_count
        print(f'We have {own} {main_asset}')

        # get all prices
        res = self._get_all_tickers()
        assert res.status_code == 200
        tickers = res.json()['data']['ticker']

        # get all coins to do with main_asset
        res = self._get_market()
        good_markets = [m for m in res.json()['data'] if m['baseCurrency'] == main_asset or m['quoteCurrency'] == main_asset]
        print(good_markets)

        if res.status_code != 200:
            print(res.status_code)
            print(res.json())
            raise ValueError('Coin setup failed')

        for s in good_markets:
            if not s['enableTrading']:
                print('Not enabled')
                print(s)
                continue

            ticker = next(t for t in tickers if t['symbol'] == s['symbol'])
            start_price = ticker['last']

            # everything is done in terms of base asset
            is_base_asset = s['quoteCurrency'] == self.main_asset
            Coin(
                name=s['baseCurrency'] if is_base_asset else s['quoteCurrency'],
                symbol=s['symbol'],
                sell_side='sell' if is_base_asset else 'buy',
                buy_side='buy' if is_base_asset else 'sell',
                is_base_asset=is_base_asset,
                qty_size=s['baseIncrement'] if is_base_asset else s['quoteIncrement'],
                price_size=s['priceIncrement'],
                min_qty=s['baseMinSize'] if is_base_asset else s['quoteMinSize'],
                start_price=start_price
            )
        print('Finished setting up Coins\n')
        return True

    def buy_coin(self, coin, qty):
        """Market buys coin.

        Args:
            coin: a coin object.
            qty: a string of the quantity to buy.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.123),...]
        """
        params = {
            'clientOid': str(uuid.uuid4()),
            'side': coin.buy_side,
            'symbol': coin.symbol,
            'type': 'market',
            'tradeType': 'TRADE',
        }
        if coin.is_base_asset:
            params['funds'] = qty
        else:
            params['size'] = qty

        res = self._request('POST', '/api/v1/orders', params, signed=True)

        if res.status_code != 200:
            return None

        order_id = res.json()['data']['orderId']
        # get quantity bought
        # its okay to wait a tiny bit for this info
        while True:
            res = self._query_order(order_id)
            data = res.json()['data']
            if data['isActive']:  # not ready yet
                continue
            # ???
            # deal funds: amount of quote asset spent
            # deal size: amount of base asset
            if coin.is_base_asset:
                out = [(data['dealSize'], Decimal(data['dealFunds']) / Decimal(data['dealSize']))]
            else:
                out = [(data['dealFunds'], Decimal(data['dealSize']) / Decimal(data['dealFunds']))]
            print(out)
            break

        return out

    def sell_coin(self, coin, qty):
        """Market sells coin.

        Args:
            coin: a coin object.
            qty: a string of the quantity to sell.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.456),...]
        """
        params = {
            'clientOid': str(uuid.uuid4()),
            'side': coin.sell_side,
            'symbol': coin.symbol,
            'type': 'market',
            'tradeType': 'TRADE',
        }
        if coin.is_base_asset:
            params['size'] = qty
        else:
            params['funds'] = qty

        res = self._request('POST', '/api/v1/orders', params, signed=True)

        order_id = res.json()['data']['orderId']
        # get quantity sold
        while True:
            res = self._query_order(order_id)
            data = res.json()['data']
            if data['isActive']:  # not ready yet
                continue
            # ???
            # deal funds: amount of quote asset spent
            # deal size: amount of base asset
            if coin.is_base_asset:
                out = [(data['dealFunds'], Decimal(data['dealSize']) / Decimal(data['dealFunds']))]
            else:
                out = [(data['dealSize'], Decimal(data['dealFunds']) / Decimal(data['dealSize']))]
            print(out)
            break

        return out

    def set_sell_limit(self, coin, quantity, price):
        """Sets sell limit for coin.

        Args:
            coin: a coin object.
            quantity: a decimal of the quantity to list.
            price: a decimal of the price to put the limit at.

        Returns:
            bool: whether successful or not
        """
        if not coin.is_base_asset:
            quantity = self.format(coin.quantize_qty(Decimal(price) * Decimal(quantity)))
            price = self.format(coin.quantize_price(1 / Decimal(price)))
        params = {
            'clientOid': str(uuid.uuid4()),
            'side': coin.sell_side,
            'symbol': coin.symbol,
            'type': 'limit',
            'tradeType': 'TRADE',

            'price': price,  # per base currency
            'size': quantity,
            # 'size': ,  # ??? (base currency)
            'hidden': True  # why not?
        }

        return self._request('POST', '/api/v1/orders', params, signed=True)

    def clear_all_orders(self, coin):
        """Clears all sell orders for coin.

        Args:
            coin: a coin object.

        Returns:
           the request response object
        """
        params = {
            'symbol': coin.symbol,
            'tradeType': 'TRADE'
        }
        return self._request('DELETE', '/api/v1/orders', params, signed=True)

    def get_balance(self, name):
        """Gets current balance for named asset.

        Args:
            name: name of asset.

        Returns:
            decimal of the amount of coin.
        """
        if isinstance(name, Coin):
            name = name.name
        res = self._request('GET', '/api/v1/accounts', signed=True)
        assert res.status_code == 200

        account = next((i for i in res.json()['data'] if i['type'] == 'trade' and i['currency'] == name), None)

        if account is None:
            raise ValueError(f'None found for {name}')

        print(account)

        return account['balance']

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
        res = self._get_price(coin.symbol)
        data = res.json()['data']
        ticker = {
            'symbol': coin.symbol,
            'ask_price': data['bestAsk'],
            'bid_price': data['bestBid']
        }
        return ticker
