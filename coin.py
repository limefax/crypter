from decimal import Decimal


class Coin:
    coins = {}
    symbols = {}
    main_asset = 'BTC'

    def __init__(self, name, symbol, sell_side, buy_side, is_base_asset, qty_size, price_size, min_qty, start_price):
        assert sell_side != buy_side
        assert sell_side.lower() == 'sell' if is_base_asset else 'buy'
        assert buy_side.lower() == 'buy' if is_base_asset else 'sell'
        assert self.main_asset in symbol
        assert self.main_asset != name

        self.name = name
        self.symbol = symbol
        self.sell_side = sell_side
        self.buy_side = buy_side
        self.is_base_asset = is_base_asset
        self.qty_size = Decimal(qty_size)
        self.price_size = Decimal(price_size)
        self.min_qty = Decimal(min_qty)
        self.start_price = Decimal(start_price)

        try:
            assert self.name not in self.coins
        except AssertionError:
            print(f'Warning: {self.name} alread in coins')
            print(self.coins[self.name])

        self.coins[self.name] = self
        self.symbols[self.symbol] = self

    def __repr__(self):
        return (f'{self.__class__.__name__}('
                f'name={repr(self.name)}, '
                f'symbol={repr(self.symbol)}, '
                f'sell_side={repr(self.sell_side)}, '
                f'buy_side={repr(self.buy_side)}, '
                f'is_base_asset={repr(self.is_base_asset)}, '
                f'qty_size={repr(self.qty_size)}, '
                f'price_size={repr(self.price_size)}, '
                f'min_qty={repr(self.min_qty)}, '
                f'start_price={repr(self.start_price)}'
                f')')

    def quantize_qty(self, qty):
        """Ensure that qty is the correct step size."""
        return (qty - (qty % self.qty_size)).normalize()

    def quantize_price(self, price):
        """Ensure that price is the correct step size."""
        return (price - (price % self.price_size)).normalize()
