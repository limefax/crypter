from decimal import Decimal
import string

import requests

from binance_exchange import Binance
from kucoin_exchange import Kucoin
from coin import Coin


class colours:
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    ENDC = '\033[0m'


def log_test(message):
    print(colours.GREEN + '[T]', message + colours.ENDC)


def log_warning(message):
    print(colours.WARNING + '[T]', message + colours.ENDC)


def exchange_tests(ex, base_asset, quote_asset, symbol):
    assert ex.setup_coins(quote_asset, 100)
    assert len(Coin.coins) >= 1

    coin = Coin.coins[base_asset]
    out = ex.buy_coin(coin, 99)
    assert len(out) >= 1
    assert isinstance(out, list)
    assert isinstance(out[0], tuple)
    assert out[0][0] and out[0][1]

    qty = ex.format(coin.quantize_qty(Decimal(out[0][0])))
    price = ex.format(coin.quantize_price(2 * Decimal(out[0][1])))
    res = ex.set_sell_limit(coin, qty, price)
    assert res.status_code == 200

    res = ex.clear_all_orders(coin)
    assert res.status_code == 200
    if isinstance(ex, Kucoin):
        assert len(res.json()['data']['cancelledOrderIds']) == 1
    elif isinstance(ex, Binance):
        assert len(res.json()) == 1

    balance1 = ex.get_balance(coin.name)
    balance2 = ex.get_balance(coin)
    print(balance1, out)
    assert balance1 == balance2
    # likely to fail
    try:
        assert Decimal(0.9) * Decimal(balance1) <= Decimal(out[0][0]) <= Decimal(balance1)
    except AssertionError:
        log_warning('Price not in expected range')

    ticker = ex.get_book_ticker(coin)
    assert ticker['symbol'] == symbol
    assert 'bid_price' in ticker
    assert 'ask_price' in ticker

    qty = ex.format(coin.quantize_qty(Decimal(balance1)))
    out = ex.sell_coin(coin, qty)
    print(out)
    # binance test exchange will fail
    try:
        assert len(out) >= 1
        assert isinstance(out, list)
        assert isinstance(out[0], tuple)
        assert out[0][0] and out[0][1]
    except AssertionError:
        log_warning('Market sell fail')

    res = ex.clear_all_orders(coin)
    if isinstance(ex, Kucoin):
        assert res.status_code == 200
        assert len(res.json()['data']['cancelledOrderIds']) == 0
    elif isinstance(ex, Binance):
        assert res.status_code == 400
        assert res.json()['code'] == -2011
    log_test('Exchange tests passed')


def test_binance():
    b = Binance(
        'https://testnet.binance.vision',
        '',
        False
    )

    # internal tests
    main_symbol = 'BTCUSDT'
    assert not b.live
    assert isinstance(b._session, requests.Session)

    signed = b._sign_query('test')
    assert all(c in string.hexdigits for c in signed)

    exchange_info = b._get_exchange_info()
    assert 'serverTime' in exchange_info
    assert 'symbols' in exchange_info
    assert 'exchangeFilters' in exchange_info

    prices = b._get_prices()
    assert len(prices) >= 1
    assert main_symbol in prices

    account = b._get_account()
    assert account['canTrade']
    assert account['accountType'] == 'SPOT'
    assert len(account['balances']) >= 1
    assert 'SPOT' in account['permissions']

    ticker = b._get_book_ticker(main_symbol)
    assert ticker['symbol'] == main_symbol
    assert 'bidPrice' in ticker
    assert 'askPrice' in ticker

    # external tests
    exchange_tests(b, 'BTC', 'USDT', 'BTCUSDT')
    log_test('Binance tests passed')


def test_kucoin():
    print('Test creating Kucoin.')
    k = Kucoin(
        'https://openapi-sandbox.kucoin.com',
        '',
        False
    )
    # internal tests
    main_symbol = 'BTC-USDT'
    assert not k.live
    assert isinstance(k._session, requests.Session)

    assert len(k._sign_request('GET', 'test', {})) == 5

    market = k._get_market().json()['data']
    assert len(market) >= 1
    for i in ['symbol', 'baseCurrency', 'quoteCurrency']:
        assert i in market[0]

    market = k._get_market('BTC').json()['data']
    assert len(market) == 1
    for i in ['symbol', 'baseCurrency', 'quoteCurrency']:
        assert i in market[0]

    price = k._get_price(main_symbol).json()['data']
    assert 'bestAsk' in price
    assert 'bestBid' in price

    tickers = k._get_all_tickers().json()['data']['ticker']
    assert len(tickers) >= 1
    assert 'symbol' in tickers[0]
    assert 'last' in tickers[0]

    # uses auth
    # assert k._query_order(...)

    # external tests
    exchange_tests(k, 'ETH', 'USDT', 'ETH-USDT')
    log_test('Kucoin tests passed')


def main():
    test_binance()
    test_kucoin()
    log_test('All tests passed')


if __name__ == '__main__':
    main()
