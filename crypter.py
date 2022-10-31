from decimal import Decimal
import json
import time

from coin import Coin
import logman


# load configurations
with open('tokens.json') as in_file:
    text = in_file.read()
tokens = json.loads(text)

MAIN_ASSET = tokens['MAIN_ASSET']
SELL_QTY = tokens['SELL_QTY']
DELAY_TIME = tokens['DELAY_TIME']

# Enable testnet if not live
prefix = 'TEST_' if not tokens['LIVE'] else ''
logman.debug(tokens)

# setup exchange
if tokens['exchange'] == 'binance':
    from binance_exchange import Binance
    EXCHANGE = Binance(
        api_base=tokens[f'{prefix}API_BASE'],
        api_key=tokens[f'{prefix}API_KEY'],
        api_secret=tokens[f'{prefix}API_SECRET'],
        live=tokens['LIVE']
    )
elif tokens['exchange'] == 'kucoin':
    from kucoin_exchange import Kucoin
    EXCHANGE = Kucoin(
        api_base=tokens[f'{prefix}API_BASE'],
        api_key=tokens[f'{prefix}API_KEY'],
        api_secret=tokens[f'{prefix}API_SECRET'],
        api_passphrase=tokens[f'{prefix}API_PASSPHRASE'],
        live=tokens['LIVE']
    )
else:
    raise ValueError(f'Invalid exchange found: {tokens["exchange"]}')

# load coins
EXCHANGE.setup_coins(MAIN_ASSET, SELL_QTY)

logman.debug('Available coins:')
for coin in Coin.coins:
    logman.debug(Coin.coins[coin])

logman.info(f'There are {len(Coin.coins)} coins')
logman.info(f'We will sell {SELL_QTY} {MAIN_ASSET}')
logman.info(f'Our market cancel time is {DELAY_TIME}')


def buy_coin(coin):
    """Buy coin at market price."""
    sell_qty = SELL_QTY
    fills = EXCHANGE.buy_coin(coin, sell_qty)
    if fills is None:
        raise SystemExit("Mission failed, could not execute market buy!")
    else:
        # work out how much we bought and for what price
        total_qty = Decimal('0')
        average_price = Decimal('0')
        for fill in fills:
            qty = Decimal(fill[0])
            price = Decimal(fill[1])
            total_qty += qty
            average_price += qty * price
            logman.info(f'Bought {qty} @ {price}')

        average_price /= total_qty
        logman.info(f'We bought {total_qty} on average @ {average_price}')

        return total_qty, average_price


def set_limit(coin, average_price, limit_qty, limit_price):
    """Set sell limit for coin."""
    average_price = 0
    # ensure correct format
    limit_qty = EXCHANGE.format(limit_qty)

    logman.info(f'Sell limit: {limit_qty} @ {limit_price}')
    limit_price = "{:f}".format(limit_price)

    res = EXCHANGE.set_sell_limit(coin, limit_qty, limit_price)
    logman.info(res.json())


def sell_coin(coin):
    """Market sell coin."""
    # cancel all orders
    logman.info('\nClear all orders')
    EXCHANGE.clear_all_orders(coin)
    time.sleep(0.1)  # ensure order is fully canceled

    logman.info('\nGet balance')
    total_qty = Decimal(EXCHANGE.get_balance(coin))
    if total_qty < coin.min_qty:
        logman.error('Too small sell qty')
        return

    logman.info(f'We have {total_qty} left over')

    if total_qty == 0:
        logman.info('SOLD ALL!')
    else:
        # market everything
        # ensure that we can pay fees
        qty = Decimal('0.99') * total_qty
        # ensure step size and format
        market_qty = EXCHANGE.format(coin.quantize_qty(qty))
        fills = EXCHANGE.sell_coin(coin, market_qty)
        logman.info(fills)

        for fill in fills:
            logman.info(f'Bought {fill[0]} {MAIN_ASSET} @ {fill[1]}')
