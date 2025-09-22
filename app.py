from fyers_apiv3 import fyersModel
import os
import json

class FyersAPI:
    def __init__(self, client_id, access_token):
        self.client_id = client_id
        self.access_token = access_token
        self.fyers = self._initialize_fyers_model()

    def _initialize_fyers_model(self):
        """Initializes the FyersModel with the provided credentials."""
        if not self.client_id or not self.access_token:
            raise ValueError("Fyers client_id and access_token must be provided.")
        return fyersModel.FyersModel(
            client_id=self.client_id,
            is_async=False, # We'll keep it synchronous for simplicity in the proxy
            token=self.access_token,
            log_path=""
        )

    def get_historical_data(self, symbol, resolution="D", range_from=None, range_to=None, cont_flag="1"):
        """Fetches historical data for a given symbol."""
        data = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": "0", # Unix timestamp
            "range_from": str(range_from), # Unix timestamp string
            "range_to": str(range_to),     # Unix timestamp string
            "cont_flag": cont_flag
        }
        try:
            response = self.fyers.history(data=data)
            if response and response.get("s") == "ok":
                return response.get("candles", [])
            else:
                print(f"Error fetching historical data for {symbol}: {response}")
                return None
        except Exception as e:
            print(f"Exception in get_historical_data for {symbol}: {e}")
            return None

    def get_quotes(self, symbols):
        """Fetches quotes for given symbols."""
        if not isinstance(symbols, str):
            symbols = ",".join(symbols) # Join list of symbols into a comma-separated string
        data = {"symbols": symbols}
        try:
            response = self.fyers.quotes(data=data)
            if response and response.get("s") == "ok":
                # Returns a list of dicts, each containing 'n' (symbol) and 'v' (value data)
                return {item['n']: item['v'] for item in response.get("d", []) if item.get('s') == 'ok'}
            else:
                print(f"Error fetching quotes for {symbols}: {response}")
                return None
        except Exception as e:
            print(f"Exception in get_quotes for {symbols}: {e}")
            return None

    def get_market_depth(self, symbol, ohlcv_flag="1"):
        """Fetches market depth for a given symbol."""
        data = {
            "symbol": symbol,
            "ohlcv_flag": ohlcv_flag
        }
        try:
            response = self.fyers.depth(data=data)
            if response and response.get("s") == "ok" and symbol in response.get("d", {}):
                return response["d"][symbol]
            else:
                print(f"Error fetching market depth for {symbol}: {response}")
                return None
        except Exception as e:
            print(f"Exception in get_market_depth for {symbol}: {e}")
            return None

    def get_option_chain(self, symbol, strikecount=1, timestamp=""):
        """Fetches option chain data for a given symbol."""
        data = {
            "symbol": symbol,
            "strikecount": strikecount,
            "timestamp": timestamp
        }
        try:
            response = self.fyers.optionchain(data=data)
            if response and response.get("s") == "ok":
                return response.get("data")
            else:
                print(f"Error fetching option chain for {symbol}: {response}")
                return None
        except Exception as e:
            print(f"Exception in get_option_chain for {symbol}: {e}")
            return None

    # You can add the WebSocket logic here, but it's more complex for a simple REST proxy.
    # For real-time, consider a separate websocket client process or a more advanced async framework.
    # For now, we'll focus on REST endpoints.
