import os
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws, order_ws
from fyers_auth import FyersAuthenticator # Import your authenticator

# Load environment variables from .env file (for local testing)
load_dotenv()

app = Flask(__name__)

# --- Configuration (from environment variables) ---
FYERS_CLIENT_ID = os.getenv("FYERS_CLIENT_ID")
FYERS_SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Your Gemini API Key

# Initialize Fyers Authenticator (global for the Flask app)
fyers_authenticator = FyersAuthenticator(FYERS_CLIENT_ID, FYERS_SECRET_KEY, FYERS_REDIRECT_URI)
fyers_api_client = None # Will be initialized after successful token generation

# --- Gemini API Integration (Placeholder) ---
# In a real scenario, you'd use the actual Google Gemini SDK
# For this example, we'll simulate a response.
def analyze_data_with_gemini(market_data):
    """
    Placeholder for Gemini API call.
    Receives market_data and returns analysis/signals.
    """
    print(f"Sending data to Gemini for analysis: {market_data}")
    # Here you would use the actual Gemini SDK to interact with your model
    # For example:
    # from google.generativeai import GenerativeModel
    # model = GenerativeModel('gemini-pro')
    # response = model.generate_content(f"Analyze this trading data: {market_data}. Provide scalping signals.")
    # return response.text

    # Simulate Gemini's response for demonstration
    time.sleep(1) # Simulate network latency
    if "candles" in market_data and len(market_data["candles"]) > 0:
        latest_candle = market_data["candles"][-1]
        close_price = latest_candle[4]
        volume = latest_candle[5]

        signal = "HOLD"
        reason = "Market is stable."

        if close_price > 500 and volume > 10000000:
            signal = "BUY"
            reason = "Strong upward momentum and high volume."
        elif close_price < 400 and volume > 5000000:
            signal = "SELL"
            reason = "Downward trend with significant selling pressure."

        return {
            "signal": signal,
            "analysis": f"Based on the latest candle (Close: {close_price}, Volume: {volume}), the analysis suggests: {reason}",
            "raw_data": market_data
        }
    else:
        return {
            "signal": "NEUTRAL",
            "analysis": "No sufficient data to generate a signal.",
            "raw_data": market_data
        }

# --- Fyers Authentication and Token Refresh (for server startup) ---
# This part is critical for Render deployment.
# On Render, your server might restart, so you need a way to get the access token.
# Option 1: Manual Input (not ideal for production)
# Option 2: Store access_token in a persistent ENV var (requires manual update if expired)
# Option 3: Implement a refresh token flow (Fyers might not have this directly for v3, check docs)
# Option 4: Re-authenticate on startup if possible (requires storing auth_code securely)

# For simplicity, let's assume `FYERS_ACCESS_TOKEN` is set as an environment variable
# on Render after an initial manual generation or through a separate script.
# In a real deployment, you'd have a more robust token management.

@app.before_first_request
def initialize_fyers_client():
    global fyers_api_client
    access_token = os.getenv("FYERS_ACCESS_TOKEN")
    if access_token:
        fyers_authenticator.access_token = access_token
        try:
            fyers_api_client = fyers_authenticator.get_fyers_model()
            print("Fyers API client initialized successfully with existing access token.")
            # Verify token by fetching profile
            profile = fyers_api_client.get_profile()
            if profile and profile.get("s") == "ok":
                print(f"Fyers profile fetched: {profile.get('name')}")
            else:
                print(f"Error fetching Fyers profile: {profile}. Token might be invalid or expired.")
                # Implement re-authentication logic here if token is invalid
        except Exception as e:
            print(f"Error initializing Fyers API client: {e}")
            fyers_api_client = None
    else:
        print("FYERS_ACCESS_TOKEN environment variable not set. Please set it for Fyers API access.")

# --- API Endpoints for Google AI Studio Frontend ---

@app.route("/")
def home():
    return "Fyers AI Scalping Analyst Backend is running!"

@app.route("/get-scalping-signal", methods=["POST"])
def get_scalping_signal():
    if not fyers_api_client:
        return jsonify({"error": "Fyers API client not initialized. Check server logs."}), 500

    data = request.json
    symbol = data.get("symbol", "NSE:SBIN-EQ")
    resolution = data.get("resolution", "5") # Default to 5-minute candles
    range_from = data.get("range_from")
    range_to = data.get("range_to")
    cont_flag = data.get("cont_flag", "1")

    if not range_from or not range_to:
        # Calculate default range for the last hour, ending 1 minute ago for complete candles
        now_epoch = int(time.time())
        # Ensure range_to is for a *completed* minute candle
        range_to_epoch = now_epoch - (now_epoch % 60) - 60 # Current minute start - 1 minute for completed candle
        range_from_epoch = range_to_epoch - (3600 * 2) # Last 2 hours of data

        range_from = str(range_from_epoch)
        range_to = str(range_to_epoch)
        print(f"Using default range: {datetime.fromtimestamp(int(range_from))} to {datetime.fromtimestamp(int(range_to))}")

    history_data_params = {
        "symbol": symbol,
        "resolution": resolution,
        "date_format": "0", # Epoch format
        "range_from": range_from,
        "range_to": range_to,
        "cont_flag": cont_flag
    }

    try:
        print(f"Fetching historical data for {symbol}...")
        history_response = fyers_api_client.history(data=history_data_params)

        if history_response and history_response.get("s") == "ok":
            print("Historical data fetched successfully. Sending to Gemini...")
            gemini_analysis = analyze_data_with_gemini(history_response)
            return jsonify(gemini_analysis)
        else:
            print(f"Error fetching historical data: {history_response}")
            return jsonify({"error": "Failed to fetch historical data from Fyers.", "details": history_response}), 500

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"error": f"An internal server error occurred: {str(e)}"}), 500

# --- WebSocket Data Streaming (Advanced - for real-time analysis) ---
# This part is more complex to integrate directly into a simple Flask server
# because WebSockets are persistent connections, while Flask handles HTTP requests.
# You'd typically run the WebSocket client in a separate thread or process,
# and it would store data or push it to a message queue for the Flask app to consume,
# or for a separate AI worker to analyze in real-time.

# For a basic setup, we'll focus on the HTTP API for historical data queries.
# If you need real-time scalping, the WebSocket integration would look something like this:

fyers_data_socket = None
fyers_order_socket = None

def start_data_websocket():
    global fyers_data_socket
    if not fyers_authenticator.access_token:
        print("Cannot start data WebSocket: Access token not available.")
        return

    def onmessage(message):
        print("WS Data Response:", message)
        # Here, push this real-time data to a queue or database
        # for your AI model to pick up and analyze for instant signals.

    def onerror(message):
        print("WS Data Error:", message)

    def onclose(message):
        print("WS Data Connection closed:", message)

    def onopen_data_ws():
        print("WS Data Connection opened. Subscribing to symbols.")
        symbols = ['NSE:SBIN-EQ', 'NSE:ADANIENT-EQ'] # Example symbols
        fyers_data_socket.subscribe(symbols=symbols, data_type="SymbolUpdate")
        # fyers_data_socket.keep_running() # This blocks, run in a separate thread

    print("Attempting to start Fyers Data WebSocket...")
    fyers_data_socket = data_ws.FyersDataSocket(
        access_token=fyers_authenticator.access_token,
        log_path="",
        litemode=False,
        write_to_file=False,
        reconnect=True,
        on_connect=onopen_data_ws,
        on_close=onclose,
        on_error=onerror,
        on_message=onmessage
    )
    # Connect in a separate thread to not block the Flask app
    import threading
    ws_thread = threading.Thread(target=fyers_data_socket.connect)
    ws_thread.start()
    print("Fyers Data WebSocket thread started.")

# You can add an endpoint to trigger this or have it start on server boot if needed.
# @app.route("/start-data-websocket", methods=["POST"])
# def trigger_start_data_ws():
#     start_data_websocket()
#     return jsonify({"message": "Attempting to start data WebSocket."})


# --- Run the Flask App ---
if __name__ == '__main__':
    # For local development, this will run on http://127.0.0.1:5000
    # For Render, it will run on the port Render assigns (usually PORT env var)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
