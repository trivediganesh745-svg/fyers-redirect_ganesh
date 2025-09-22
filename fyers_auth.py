import os
from fyers_apiv3 import fyersModel
import time
import requests

class FyersAuthenticator:
    def __init__(self, client_id, secret_key, redirect_uri):
        self.client_id = client_id
        self.secret_key = secret_key
        self.redirect_uri = redirect_uri
        self.fyers_model = None
        self.access_token = None

    def get_auth_code_url(self):
        """Generates the Fyers login URL for manual authorization."""
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        return session.generate_authcode()

    def generate_access_token(self, auth_code):
        """Generates the access token using the auth_code."""
        session = fyersModel.SessionModel(
            client_id=self.client_id,
            secret_key=self.secret_key,
            redirect_uri=self.redirect_uri,
            response_type="code",
            grant_type="authorization_code"
        )
        session.set_token(auth_code)
        response = session.generate_token()

        if response and response.get("access_token"):
            self.access_token = response["access_token"]
            # Store the access token securely (e.g., in an environment variable or a secure database)
            # For Render, you might need to re-authenticate periodically or use a refresh token mechanism
            # For this example, we'll assume a relatively long-lived token or re-auth on startup
            print("Access Token generated successfully!")
            return self.access_token
        else:
            print(f"Error generating access token: {response}")
            return None

    def get_fyers_model(self):
        """Returns an initialized FyersModel object."""
        if not self.access_token:
            raise Exception("Access token not generated. Please run authentication first.")
        if not self.fyers_model:
            self.fyers_model = fyersModel.FyersModel(
                token=self.access_token,
                is_async=False, # Set to True if you want async operations
                client_id=self.client_id,
                log_path=""
            )
        return self.fyers_model

# Example of how to use it (for local testing or initial setup)
if __name__ == "__main__":
    # These should ideally come from environment variables in production
    CLIENT_ID = os.getenv("FYERS_CLIENT_ID") # e.g., "XCXXXXXxxM-100"
    SECRET_KEY = os.getenv("FYERS_SECRET_KEY") # e.g., "MH*****TJ5"
    REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI") # e.g., "https://myredirecturl.com"

    authenticator = FyersAuthenticator(CLIENT_ID, SECRET_KEY, REDIRECT_URI)

    # Step 1: Get the auth code URL
    auth_code_url = authenticator.get_auth_code_url()
    print(f"Please open this URL in your browser and get the auth code: {auth_code_url}")
    # In a production setup, you would direct the user to this URL and capture the redirect.
    # For a server, you might need to manually get this initially or implement a more complex OAuth flow.

    # Step 2: Manually paste the auth_code here after logging in via the browser
    # For a server, you'd have an endpoint to receive this auth_code from the redirect URI.
    manual_auth_code = input("Enter the auth_code from the browser URL: ")

    access_token = authenticator.generate_access_token(manual_auth_code)
    if access_token:
        print(f"Generated Access Token: {access_token}")
        # Now you can use authenticator.get_fyers_model() to make API calls
        fyers = authenticator.get_fyers_model()
        print(fyers.get_profile())
