import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, redirect, session, jsonify, render_template
# Changed to fyers_apiv3 as per your snippets
from fyers_apiv3 import fyersModel, accessToken 
# You'll need this for WebSocket if you use it in the proxy
from fyers_apiv3.FyersWebsocket import data_ws 

app = Flask(__name__)
app.secret_key = os.urandom(24) # Set a secret key for session management

# Fyers API Configuration (replace with your actual credentials)
CLIENT_ID = os.environ.get("FYERS_CLIENT_ID", "YOUR_CLIENT_ID-100") # Use environment variables for security
CLIENT_ID_WITHOUT_100 = CLIENT_ID.split("-")[0]
SECRET_KEY = os.environ.get("FYERS_SECRET_KEY", "YOUR_SECRET_KEY")
REDIRECT_URI = "http://127.0.0.1:5000/fyers-auth-callback" # Adjust if your proxy runs on a different port/domain

# Global variables to store token and FyersModel instance
# It's better to manage these in a more robust way for production,
# e.g., persistent storage, but globals are fine for a simple proxy example.
ACCESS_TOKEN = None
REFRESH_TOKEN = None
fyers_instance = None # Renamed to avoid conflict with the module name

# --- Fyers API Initialization Helper ---
def initialize_fyers_model(token):
    global fyers_instance # Declare fyers_instance as global here
    if token:
        # Use fyersModel from fyers_apiv3
        fyers_instance = fyersModel.FyersModel(token=token, is_async=False, client_id=CLIENT_ID, log_path="")
        print("FyersModel initialized with access token.")
    else:
        print("FyersModel could not be initialized: No access token provided.")

def _get_fyers_instance():
    """Returns the initialized FyersModel instance, or None if not initialized."""
    global fyers_instance
    if not fyers_instance and ACCESS_TOKEN:
        # Attempt to initialize if ACCESS_TOKEN exists but instance doesn't
        initialize_fyers_model(ACCESS_TOKEN)
    return fyers_instance

# --- Web Application Routes ---

@app.route('/')
def index():
    if ACCESS_TOKEN and _get_fyers_instance():
        return render_template('dashboard.html')
    return render_template('index.html')

@app.route('/login')
def login():
    session_builder = accessToken.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    response_url = session_builder.generate_authcode()
    return redirect(response_url)

@app.route('/fyers-auth-callback')
def fyers_auth_callback():
    auth_code = request.args.get('auth_code')
    if not auth_code:
        return jsonify({"error": "Authorization code not found in callback."}), 400

    session_builder = accessToken.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code"
    )
    session_builder.set_token(auth_code)

    try:
        response = session_builder.generate_token()
        
        global ACCESS_TOKEN # Declare ACCESS_TOKEN as global here
        global REFRESH_TOKEN # Declare REFRESH_TOKEN as global here
        
        ACCESS_TOKEN = response["access_token"]
        REFRESH_TOKEN = response.get("refresh_token") # Refresh token might not always be present
        
        initialize_fyers_model(ACCESS_TOKEN) # This will handle 'global fyers_instance'
        
        print(f"Access Token: {ACCESS_TOKEN}")
        print(f"Refresh Token: {REFRESH_TOKEN}")
        
        return redirect('/') # Redirect to dashboard or home page
    except Exception as e:
        print(f"Error during token generation: {e}")
        return jsonify({"error": f"Failed to generate access token: {str(e)}"}), 500

# --- Fyers API Proxy Endpoints ---

@app.route('/api/fyers/profile')
def get_profile():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        profile_data = fyers_api.get_profile()
        return jsonify(profile_data)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching profile: {e}")
        return jsonify({"error": f"Failed to fetch profile (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/funds')
def get_funds():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        funds_data = fyers_api.funds()
        return jsonify(funds_data)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching funds: {e}")
        return jsonify({"error": f"Failed to fetch funds (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/holdings')
def get_holdings():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        holdings_data = fyers_api.holdings()
        return jsonify(holdings_data)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching holdings: {e}")
        return jsonify({"error": f"Failed to fetch holdings (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/history', methods=['POST'])
def get_history():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or not all(k in data for k in ["symbol", "resolution", "range_from", "range_to"]):
            return jsonify({"error": "Missing required parameters for history API. Need symbol, resolution, range_from, range_to."}), 400
        
        history_data = fyers_api.history(data=data) # Pass data as keyword argument
        return jsonify(history_data)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching history: {e}")
        return jsonify({"error": f"Failed to fetch history (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/place_order', methods=['POST'])
def place_single_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        order_data = request.json
        if not order_data:
            return jsonify({"error": "No order data provided."}), 400
        
        response = fyers_api.place_order(data=order_data) # Pass data as keyword argument
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error placing order: {e}")
        return jsonify({"error": f"Failed to place order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/orderbook')
def get_orderbook():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        # Check for optional orderId from query parameter
        order_id = request.args.get('orderId')
        data = {"id": order_id} if order_id else {}
        response = fyers_api.orderbook(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching orderbook: {e}")
        return jsonify({"error": f"Failed to fetch orderbook (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/orders_by_tag')
def get_orders_by_tag():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        order_tag = request.args.get('order_tag')
        if not order_tag:
            return jsonify({"error": "Missing 'order_tag' parameter."}), 400
        
        # The Fyers API v3 `orderbook` method itself has a `data` parameter
        # which can accept an 'orderTag' as per your curl example.
        # This assumes your fyersModel.orderbook implementation supports it.
        # If not, you might need to filter client-side or check Fyers docs.
        data = {"orderTag": order_tag}
        response = fyers_api.orderbook(data=data) 
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching orders by tag: {e}")
        return jsonify({"error": f"Failed to fetch orders by tag (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/positions')
def get_positions():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        response = fyers_api.positions()
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching positions: {e}")
        return jsonify({"error": f"Failed to fetch positions (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/tradebook')
def get_tradebook():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        response = fyers_api.tradebook()
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching tradebook: {e}")
        return jsonify({"error": f"Failed to fetch tradebook (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/market_status')
def get_market_status():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        response = fyers_api.market_status()
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching market status: {e}")
        return jsonify({"error": f"Failed to fetch market status (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/quotes', methods=['GET'])
def get_quotes():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        symbols_str = request.args.get('symbols')
        if not symbols_str:
            return jsonify({"error": "Missing 'symbols' query parameter."}), 400
        
        data = {"symbols": symbols_str}
        response = fyers_api.quotes(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching quotes: {e}")
        return jsonify({"error": f"Failed to fetch quotes (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/depth', methods=['POST'])
def get_depth():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "symbol" not in data:
            return jsonify({"error": "Missing 'symbol' in request body."}), 400
        
        response = fyers_api.depth(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching market depth: {e}")
        return jsonify({"error": f"Failed to fetch market depth (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/optionchain', methods=['POST'])
def get_optionchain():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "symbol" not in data:
            return jsonify({"error": "Missing 'symbol' in request body."}), 400
        
        response = fyers_api.optionchain(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching option chain: {e}")
        return jsonify({"error": f"Failed to fetch option chain (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/place_basket_orders', methods=['POST'])
def place_basket_orders():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        orders_data = request.json
        if not isinstance(orders_data, list) or not orders_data:
            return jsonify({"error": "Request body must be a non-empty list of order objects."}), 400
        
        response = fyers_api.place_basket_orders(data=orders_data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error placing basket orders: {e}")
        return jsonify({"error": f"Failed to place basket orders (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/place_multileg_order', methods=['POST'])
def place_multileg_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "legs" not in data:
            return jsonify({"error": "Missing 'legs' in request body."}), 400
        
        response = fyers_api.place_multileg_order(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error placing multileg order: {e}")
        return jsonify({"error": f"Failed to place multileg order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/place_gtt_order', methods=['POST'])
def place_gtt_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "orderInfo" not in data:
            return jsonify({"error": "Missing 'orderInfo' in request body."}), 400
        
        response = fyers_api.place_gtt_order(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error placing GTT order: {e}")
        return jsonify({"error": f"Failed to place GTT order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/modify_gtt_order', methods=['POST'])
def modify_gtt_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "id" not in data or "orderInfo" not in data:
            return jsonify({"error": "Missing 'id' or 'orderInfo' in request body."}), 400
        
        response = fyers_api.modify_gtt_order(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error modifying GTT order: {e}")
        return jsonify({"error": f"Failed to modify GTT order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/cancel_gtt_order', methods=['POST'])
def cancel_gtt_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "id" not in data:
            return jsonify({"error": "Missing 'id' in request body."}), 400
        
        response = fyers_api.cancel_gtt_order(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error canceling GTT order: {e}")
        return jsonify({"error": f"Failed to cancel GTT order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/gtt_orderbook')
def get_gtt_orderbook():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        response = fyers_api.gtt_orderbook()
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error fetching GTT orderbook: {e}")
        return jsonify({"error": f"Failed to fetch GTT orderbook (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/modify_order', methods=['POST'])
def modify_single_order():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or "id" not in data:
            return jsonify({"error": "Missing 'id' in request body."}), 400
        
        response = fyers_api.modify_order(data=data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error modifying single order: {e}")
        return jsonify({"error": f"Failed to modify single order (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/modify_basket_orders', methods=['POST'])
def modify_basket_orders():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        orders_data = request.json
        if not isinstance(orders_data, list) or not orders_data:
            return jsonify({"error": "Request body must be a non-empty list of order modification objects."}), 400
        
        response = fyers_api.modify_basket_orders(data=orders_data)
        return jsonify(response)
    except Exception as e:
        ACCESS_TOKEN = None
        fyers_instance = None
        print(f"Error modifying basket orders: {e}")
        return jsonify({"error": f"Failed to modify basket orders (token might be invalid/expired): {str(e)}"}), 401

@app.route('/api/fyers/logout')
def logout_fyers():
    global ACCESS_TOKEN
    global fyers_instance
    fyers_api = _get_fyers_instance()
    if not fyers_api:
        # If fyers_api is not initialized, consider it already logged out or no session
        ACCESS_TOKEN = None
        fyers_instance = None
        return jsonify({"s": "ok", "code": 200, "message": "Already logged out or no active session."})
    try:
        response = fyers_api.logout()
        ACCESS_TOKEN = None
        fyers_instance = None
        return jsonify(response)
    except Exception as e:
        print(f"Error during logout: {e}")
        # Even if logout fails on Fyers side, clear local session
        ACCESS_TOKEN = None
        fyers_instance = None
        return jsonify({"error": f"Failed to logout: {str(e)}"}), 500


# --- Placeholder for Gemini API Integration ---
@app.route('/api/gemini/analyze', methods=['POST'])
def analyze_with_gemini():
    # This is where you would integrate with the Gemini API.
    # 1. Receive Fyers data from your frontend (e.g., historical data, positions, etc.)
    fyers_data = request.json
    if not fyers_data:
        return jsonify({"error": "No data provided for Gemini analysis."}), 400

    # 2. Format the data for Gemini (e.g., create a prompt)
    prompt = "Analyze the following Fyers trading data and provide insights: " + json.dumps(fyers_data)

    # 3. Call the Gemini API
    #    You'll need to install google-generativeai: pip install google-generativeai
    #    And set up your API key.
    #
    # import google.generativeai as genai
    # genai.configure(api_key="YOUR_GEMINI_API_KEY")
    # model = genai.GenerativeModel('gemini-pro')
    # try:
    #     gemini_response = model.generate_content(prompt)
    #     analysis_result = gemini_response.text
    #     return jsonify({"analysis": analysis_result})
    # except Exception as e:
    #     print(f"Error calling Gemini API: {e}")
    #     return jsonify({"error": f"Failed to get analysis from Gemini: {str(e)}"}), 500

    # Placeholder response
    return jsonify({"message": "Gemini analysis endpoint - placeholder. Integrate Gemini API here.", "received_data": fyers_data})


# --- Placeholder for Fyers WebSocket Integration ---
# These functions will handle WebSocket events.
# They would typically process real-time data and either store it,
# or push it to connected clients (e.g., via another WebSocket for the frontend).
def onopen(ws):
    print("WebSocket connection opened.")
    # Subscribe to symbols here if you want immediate data
    # fyers.subscribe(symbols=['NSE:SBIN-EQ', 'NSE:IDEA-EQ'], data_type='symbolData')

def onclose(ws):
    print("WebSocket connection closed.")

def onerror(ws, msg):
    print(f"WebSocket error: {msg}")

def onmessage(ws, msg):
    print(f"WebSocket message received: {msg}")
    # Here you would process the real-time data
    # and potentially send it to your frontend or store it.

def start_fyers_websocket():
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        print("Cannot start WebSocket: ACCESS_TOKEN not available.")
        return

    print("Attempting to start Fyers WebSocket...")
    try:
        # Create FyersDataSocket instance
        # The access_token format is usually "APP_ID:ACCESS_TOKEN"
        # Ensure your ACCESS_TOKEN is formatted correctly.
        ws_access_token = f"{CLIENT_ID_WITHOUT_100}:{ACCESS_TOKEN}"
        
        fyers_ws = data_ws.FyersDataSocket(
            access_token=ws_access_token,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=onopen,
            on_close=onclose,
            on_error=onerror,
            on_message=onmessage,
            reconnect_retry=10
        )
        
        # Start the WebSocket connection in a non-blocking way
        # This will usually run in a separate thread or process
        # For a simple Flask app, you might consider using a library like Flask-SocketIO
        # or running this in a separate thread.
        # For now, just call connect() - it might block if not handled carefully.
        fyers_ws.connect()
        print("Fyers WebSocket connected.")

    except Exception as e:
        print(f"Error starting Fyers WebSocket: {e}")


# --- Main Execution ---
if __name__ == '__main__':
    # You might want to uncomment this to automatically start the WebSocket
    # after the server runs and an ACCESS_TOKEN is available.
    # However, integrating WebSockets properly with Flask requires more advanced patterns
    # (e.g., using Flask-SocketIO or a separate thread/process for the WebSocket client)
    # to prevent blocking the main Flask thread.
    # For now, it's just a callable function.
    # start_fyers_websocket() 
    app.run(debug=True) # debug=True is good for development, set to False for production
