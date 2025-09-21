import os
from flask import Flask, request, jsonify, redirect, url_for
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv
from flask_cors import CORS
import google.generativeai as genai
import json # Ensure json is imported

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# --- Fyers API Configuration ---
CLIENT_ID = os.environ.get("FYERS_CLIENT_ID")
SECRET_KEY = os.environ.get("FYERS_SECRET_KEY")
REDIRECT_URI = os.environ.get("FYERS_REDIRECT_URI")
ACCESS_TOKEN = os.environ.get("FYERS_ACCESS_TOKEN")

# Frontend URL - **IMPORTANT: ADD THIS ENVIRONMENT VARIABLE**
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8000") # Default for local testing

if not all([CLIENT_ID, SECRET_KEY, REDIRECT_URI]):
    print("WARNING: Fyers API credentials are not fully set. Some functionalities may not work.")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY is not set. Gemini API functionality will not work.")

# Initialize FyersModel (global)
fyers = None

def initialize_fyers_model(token):
    global fyers
    if token:
        fyers = fyersModel.FyersModel(token=token, is_async=False, client_id=CLIENT_ID, log_path="")
        print("FyersModel initialized with access token.")
    else:
        print("FyersModel could not be initialized: No access token provided.")

initialize_fyers_model(ACCESS_TOKEN)

# --- Gemini API Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')

# --- Fyers Authentication Flow Endpoints ---

@app.route('/fyers-login')
def fyers_login():
    """
    Initiates the Fyers authentication flow.
    Redirects the user to the Fyers login page.
    """
    if not CLIENT_ID or not REDIRECT_URI or not SECRET_KEY:
        return jsonify({"error": "Fyers API credentials not fully configured on the server."}), 500

    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        state="fyers_proxy_state",
        secret_key=SECRET_KEY,
        grant_type="authorization_code"
    )
    generate_token_url = session.generate_authcode()
    return redirect(generate_token_url)

@app.route('/fyers-auth-callback')
def fyers_auth_callback():
    """
    Callback endpoint after the user logs in on Fyers.
    Exchanges the auth_code for an access_token.
    """
    auth_code = request.args.get('auth_code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        # Redirect to frontend with error
        return redirect(f"{FRONTEND_URL}?fyers_auth_status=failed&error={error}")
    if not auth_code:
        # Redirect to frontend with error
        return redirect(f"{FRONTEND_URL}?fyers_auth_status=failed&error=no_auth_code")

    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        state=state,
        secret_key=SECRET_KEY,
        grant_type="authorization_code"
    )
    session.set_token(auth_code)
    try:
        response = session.generate_token()
        new_access_token = response["access_token"]
        global ACCESS_TOKEN
        ACCESS_TOKEN = new_access_token
        initialize_fyers_model(ACCESS_TOKEN)
        
        # Redirect to frontend with success status
        return redirect(f"{FRONTEND_URL}?fyers_auth_status=success")
        
    except Exception as e:
        print(f"Error generating Fyers access token: {e} - Response: {response}")
        # Redirect to frontend with error
        return redirect(f"{FRONTEND_URL}?fyers_auth_status=failed&error={str(e)}")


# --- Fyers Data Endpoints (no changes needed for these) ---
@app.route('/api/fyers/profile')
def get_profile():
    if not fyers:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        profile_data = fyers.get_profile()
        return jsonify(profile_data)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch profile: {str(e)}"}), 500

@app.route('/api/fyers/funds')
def get_funds():
    if not fyers:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        funds_data = fyers.funds()
        return jsonify(funds_data)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch funds: {str(e)}"}), 500

@app.route('/api/fyers/holdings')
def get_holdings():
    if not fyers:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        holdings_data = fyers.holdings()
        return jsonify(holdings_data)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch holdings: {str(e)}"}), 500

@app.route('/api/fyers/history', methods=['POST'])
def get_history():
    if not fyers:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        data = request.json
        if not data or not all(k in data for k in ["symbol", "resolution", "range_from", "range_to"]):
            return jsonify({"error": "Missing required parameters for history API. Need symbol, resolution, range_from, range_to."}), 400
        
        history_data = fyers.history(data)
        return jsonify(history_data)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch history: {str(e)}"}), 500

@app.route('/api/fyers/place_order', methods=['POST'])
def place_single_order():
    if not fyers:
        return jsonify({"error": "Fyers API not initialized. Please authenticate first."}), 401
    try:
        order_data = request.json
        if not order_data:
            return jsonify({"error": "No order data provided."}), 400
        
        response = fyers.place_order(order_data)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": f"Failed to place order: {str(e)}"}), 500


# --- New Gemini AI Analysis Endpoint (no changes needed) ---
@app.route('/api/gemini/analyze', methods=['POST'])
def gemini_analyze():
    if not GOOGLE_API_KEY:
        return jsonify({"error": "Gemini API key not configured on the server."}), 500
    
    try:
        data = request.json
        market_data = data.get("market_data")
        analysis_logic = data.get("analysis_logic")

        if not market_data or not analysis_logic:
            return jsonify({"error": "Missing 'market_data' or 'analysis_logic' in request."}), 400

        prompt = f"""
        Analyze the following market data based on the provided scalping logic.
        The market data represents historical candles. Each candle is in the format:
        [timestamp (Epoch), open, high, low, close, volume]

        Market Data (last few candles for context, more detailed data will be available to the model internally):
        {market_data['candles'][-10:] if market_data and 'candles' in market_data else 'No candle data provided.'}

        Full Market Data (important for deep analysis):
        {market_data}

        Scalping Core Logic:
        {analysis_logic}

        Based on this, provide a concise intraday scalping signal.
        The output MUST be a JSON object with the following structure.
        Strictly adhere to this format.
        
        {{
            "symbol": "NSE:NIFTY50-INDEX", // Replace with the actual symbol from market_data
            "action": "BUY" | "SELL" | "HOLD",
            "entry_price": 0.0, // e.g., 130.00
            "stop_loss": 0.0, // e.g., 115.00
            "target_price": 0.0, // e.g., 275.00
            "reasoning": "BRIEF_EXPLANATION_FOR_THE_SIGNAL" // Max 2-3 sentences
        }}
        
        If no clear opportunity is found, set "action": "HOLD" and provide a reason.
        Ensure the prices are realistic based on the provided market data.
        """
        
        response = gemini_model.generate_content(prompt)
        gemini_text_response = response.text
        
        try:
            signal = json.loads(gemini_text_response)
            required_keys = ["symbol", "action", "entry_price", "stop_loss", "target_price", "reasoning"]
            if not all(key in signal for key in required_keys):
                raise ValueError("Gemini response is not in the expected JSON format.")
            
            return jsonify({"signal": signal})
        except json.JSONDecodeError:
            print(f"Gemini response was not valid JSON: {gemini_text_response}")
            return jsonify({"error": "Gemini response was not valid JSON. Please check prompt formatting.", "gemini_raw_response": gemini_text_response}), 500
        except ValueError as ve:
            print(f"Gemini response parsing error: {ve} - Raw: {gemini_text_response}")
            return jsonify({"error": str(ve), "gemini_raw_response": gemini_text_response}), 500

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return jsonify({"error": f"Failed to perform AI analysis: {str(e)}"}), 500


@app.route('/')
def home():
    # This route is mainly for a quick check that the proxy is running.
    # The frontend will be loaded from its own URL.
    return "Fyers API Proxy Server is running! Access the frontend to use it."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
