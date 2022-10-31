from abc import ABC, abstractmethod


class Exchange(ABC):
    @abstractmethod
    def setup_coins(self, main_asset, main_asset_count):
        """Setups the coin structure.

        Also checks that we have enough main_asset.

        Args:
            main_asset: string of the asset to buy coin with.
            main_asset_count: string of number of main_asset to use to buy coin.
        """
        pass

    @abstractmethod
    def buy_coin(self, coin, qty):
        """Market buys coin.

        Args:
            coin: a coin object.
            qty: a string of the quantity to buy.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.123),...]
        """
        pass

    @abstractmethod
    def sell_coin(self, coin, qty):
        """Market sells coin.

        Args:
            coin: a coin object.
            qty: a string of the quantity to sell.

        Returns:
            A list of tuples in the form (quantity, price).

            [(500, 0.456),...]
        """
        pass

    @abstractmethod
    def set_sell_limit(self, coin, quantity, price):
        """Sets sell limit for coin.

        Args:
            coin: a coin object.
            quantity: a decimal of the quantity to list.
            price: a decimal of the price to put the limit at.

        Returns:
            res
        """
        pass

    @abstractmethod
    def clear_all_orders(self, coin):
        """Clears all sell orders for coin.

        Args:
            coin: a coin object.

        Returns:
            the number of coin left over
        """
        pass

    @abstractmethod
    def get_balance(self, name):
        """Gets current balance for named asset.

        Args:
            name: name of asset.

        Returns:
            decimal of the amount of coin.
        """
        pass

    @abstractmethod
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
        pass

    @staticmethod
    def format(value):
        return '{:f}'.format(value)
