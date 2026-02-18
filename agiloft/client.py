"""
Agiloft API Client

Handles authentication, session management, and API calls to Agiloft REST API.
Automatically manages token refresh for the 15-minute expiration window.
"""

import aiohttp
import asyncio
import html
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
# Handle both direct execution and package imports
try:
    from .config import Config
    from .exceptions import AgiloftAuthError, AgiloftAPIError
except ImportError:
    from config import Config
    from exceptions import AgiloftAuthError, AgiloftAPIError

logger = logging.getLogger(__name__)

class AgiloftClient:
    """Agiloft REST API client with automatic authentication and token refresh."""

    def __init__(self, config: Config):
        self.config = config
        self.base_url = config.get('agiloft.base_url')
        self.kb = config.get('agiloft.kb')
        self.language = config.get('agiloft.language', 'en')

        # Authentication method
        self.auth_method = config.get('agiloft.auth_method', 'legacy')

        # Legacy authentication credentials
        self.username = config.get('agiloft.username')
        self.password = config.get('agiloft.password')

        # OAuth2 credentials
        self.oauth2_client_id = config.get('agiloft.oauth2.client_id')
        self.oauth2_client_secret = config.get('agiloft.oauth2.client_secret')
        self.oauth2_token_endpoint = config.get('agiloft.oauth2.token_endpoint')
        self.oauth2_authorization_endpoint = config.get('agiloft.oauth2.authorization_endpoint')
        self.oauth2_redirect_uri = config.get('agiloft.oauth2.redirect_uri', 'http://localhost:8080/callback')
        self.oauth2_scope = config.get('agiloft.oauth2.scope', '')

        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.api_access_point: Optional[str] = None
        self._auth_lock = asyncio.Lock()
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def ensure_session(self):
        """Ensure HTTP session is created."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def ensure_authenticated(self):
        """Ensure we have a valid authentication token."""
        async with self._auth_lock:
            # Check if we need to authenticate or refresh
            now = datetime.now()

            if (self.access_token is None or
                self.token_expires_at is None or
                now >= self.token_expires_at - timedelta(minutes=1)):  # Refresh 1 min early

                # Try token refresh first if we have a refresh token
                if self.refresh_token:
                    try:
                        await self._refresh_access_token()
                        return
                    except AgiloftAuthError as e:
                        logger.warning(f"Token refresh failed, falling back to authentication: {e}")
                        self.refresh_token = None

                await self._authenticate()
                
    async def _authenticate(self):
        """Perform authentication with Agiloft API."""
        if self.auth_method == "oauth2_client_credentials":
            await self._authenticate_oauth2_client_credentials()
        elif self.auth_method == "oauth2_authorization_code":
            # Try refresh token if available before requiring browser auth
            if self.refresh_token:
                try:
                    await self._refresh_access_token()
                    return
                except AgiloftAuthError as e:
                    logger.warning(f"Token refresh failed in _authenticate: {e}")
                    self.refresh_token = None

            # For authorization code flow, the user must call authenticate_with_browser() first
            raise AgiloftAuthError(
                "OAuth2 Authorization Code flow requires manual authentication. "
                "Call authenticate_with_browser() before using the client."
            )
        else:
            await self._authenticate_legacy()

    async def _authenticate_legacy(self):
        """Perform legacy username/password authentication with Agiloft API."""
        await self.ensure_session()

        login_url = f"{self.base_url}/login"
        login_data = {
            "password": self.password,
            "KB": self.kb,
            "login": self.username,
            "lang": self.language
        }

        logger.info("Authenticating with Agiloft (legacy method)...")

        try:
            async with self.session.post(login_url, json=login_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    error_msg = f"Authentication failed: {response.status} - {error_text}"
                    logger.error(f"{error_msg} (URL: {login_url}, Username: {self.username}, KB: {self.kb})")
                    raise AgiloftAuthError(error_msg)

                data = await response.json()

                if not data.get('success', False):
                    error_msg = f"Authentication failed: {data.get('message', 'Unknown error')}"
                    logger.error(f"{error_msg} (Username: {self.username}, KB: {self.kb}, Response: {data})")
                    raise AgiloftAuthError(error_msg)

                result = data.get('result', {})
                self.access_token = result.get('access_token')
                self.refresh_token = result.get('refresh_token')
                expires_in = result.get('expires_in', 900)  # Default 900 seconds (15 minutes)

                # Calculate expiration time (Agiloft returns expires_in in seconds)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                logger.info(f"Authentication successful. Token expires at {self.token_expires_at}")

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise

    async def _authenticate_oauth2_client_credentials(self):
        """Perform OAuth2 client credentials authentication."""
        await self.ensure_session()

        logger.info("Authenticating with Agiloft (OAuth2 client credentials)...")

        # Prepare OAuth2 token request
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.oauth2_client_id,
            "client_secret": self.oauth2_client_secret,
            "kb": self.kb
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        try:
            async with self.session.post(
                self.oauth2_token_endpoint,
                data=token_data,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    error_msg = f"OAuth2 authentication failed: {response.status} - {error_text}"
                    logger.error(f"{error_msg} (Token Endpoint: {self.oauth2_token_endpoint}, Client ID: {self.oauth2_client_id})")
                    raise AgiloftAuthError(error_msg)

                data = await response.json()

                # OAuth2 standard response format
                self.access_token = data.get('access_token')
                if not self.access_token:
                    error_msg = f"No access token in OAuth2 response: {data}"
                    logger.error(error_msg)
                    raise AgiloftAuthError(error_msg)

                # Token expiration (Agiloft returns expires_in in seconds)
                expires_in = data.get('expires_in', 900)  # Default 900 seconds (15 minutes)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                # Refresh token (optional for client credentials flow)
                self.refresh_token = data.get('refresh_token')

                logger.info(f"OAuth2 authentication successful. Token expires at {self.token_expires_at}")

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"OAuth2 authentication error: {str(e)}")
            raise AgiloftAuthError(f"OAuth2 authentication failed: {str(e)}")

    async def authenticate_with_browser(self) -> bool:
        """
        Perform OAuth2 Authorization Code flow authentication.
        Opens a browser for user to log in, then exchanges code for token.

        Returns:
            bool: True if authentication was successful

        Raises:
            AgiloftAuthError: If authentication fails
        """
        import webbrowser
        import secrets
        import urllib.parse
        from aiohttp import web

        logger.info("Starting OAuth2 Authorization Code flow...")

        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)

        # Build authorization URL
        auth_params = {
            'client_id': self.oauth2_client_id,
            'redirect_uri': self.oauth2_redirect_uri,
            'response_type': 'code',
            'state': state
        }

        # Add scope if provided
        if self.oauth2_scope:
            auth_params['scope'] = self.oauth2_scope

        auth_url = f"{self.oauth2_authorization_endpoint}?{urllib.parse.urlencode(auth_params)}"

        logger.info(f"Opening browser for authorization...")
        logger.info(f"Authorization URL: {auth_url}")

        # Store the authorization code and API access point
        auth_code = None
        received_state = None
        api_access_point = None

        # Create a simple HTTP server to receive the callback
        async def handle_callback(request):
            nonlocal auth_code, received_state, api_access_point

            # Get query parameters
            params = request.rel_url.query
            auth_code = params.get('code')
            received_state = params.get('state')
            api_access_point = params.get('api_access_point', '')
            error = params.get('error')

            if error:
                logger.error(f"Authorization error: {error}")
                safe_error = html.escape(str(error))
                return web.Response(
                    text=f"<html><body><h1>Authorization Failed</h1><p>Error: {safe_error}</p><p>You can close this window.</p></body></html>",
                    content_type='text/html'
                )

            if not auth_code:
                logger.error("No authorization code received")
                return web.Response(
                    text="<html><body><h1>Authorization Failed</h1><p>No authorization code received</p><p>You can close this window.</p></body></html>",
                    content_type='text/html'
                )

            logger.info("Authorization code received successfully")
            return web.Response(
                text="<html><body><h1>Authorization Successful!</h1><p>You can close this window and return to the application.</p></body></html>",
                content_type='text/html'
            )

        # Parse redirect URI to get port
        from urllib.parse import urlparse
        parsed_uri = urlparse(self.oauth2_redirect_uri)
        port = parsed_uri.port or 8080

        # Create and start the server
        app = web.Application()
        app.router.add_get(parsed_uri.path, handle_callback)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, 'localhost', port)
        await site.start()

        logger.info(f"Callback server started on port {port}")

        # Open browser
        webbrowser.open(auth_url)

        # Wait for the callback (with timeout)
        timeout = 300  # 5 minutes
        import time
        start_time = time.time()

        while auth_code is None and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.5)

        # Stop the server
        await runner.cleanup()

        if auth_code is None:
            raise AgiloftAuthError("Authorization timeout - no code received")

        # Verify state parameter
        if received_state != state:
            raise AgiloftAuthError("State parameter mismatch - possible CSRF attack")

        # Exchange authorization code for access token
        logger.info("Exchanging authorization code for access token...")
        await self._exchange_code_for_token(auth_code, api_access_point)

        return True

    async def _exchange_code_for_token(self, auth_code: str, api_access_point: str = None):
        """Exchange authorization code for access token."""
        await self.ensure_session()

        # Store api_access_point for future token refresh requests
        if api_access_point:
            self.api_access_point = api_access_point

        # Use api_access_point if provided, otherwise use base_url
        if api_access_point:
            token_url = f"{api_access_point}/ewws/otoken"
        else:
            # Extract base URL from self.base_url
            base_url = self.base_url.split('/ewws/alrest')[0]
            token_url = f"{base_url}/ewws/otoken"

        logger.info(f"Token endpoint: {token_url}")

        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.oauth2_client_id,
            'redirect_uri': self.oauth2_redirect_uri
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        try:
            async with self.session.post(
                token_url,
                data=token_data,
                headers=headers
            ) as response:
                # Get response text first to handle both JSON and HTML responses
                response_text = await response.text()

                if response.status != 200:
                    error_msg = f"Token exchange failed: {response.status} - {response_text}"
                    logger.error(error_msg)
                    raise AgiloftAuthError(error_msg)

                # Check if response is JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.error(f"Unexpected content type: {content_type}")
                    logger.error(f"Response text: {response_text[:1000]}")
                    raise AgiloftAuthError(f"Expected JSON response but got {content_type}. Response: {response_text[:500]}")

                # Parse JSON response
                data = json.loads(response_text)

                # Extract access token
                self.access_token = data.get('access_token')
                if not self.access_token:
                    error_msg = f"No access token in response: {data}"
                    logger.error(error_msg)
                    raise AgiloftAuthError(error_msg)

                # Token expiration (despite docs saying minutes, the value appears to be in seconds)
                # Example: 900 seconds = 15 minutes (default token expiry)
                expires_in = data.get('expires_in', 900)  # Default 15 minutes in seconds
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                # Refresh token
                self.refresh_token = data.get('refresh_token')

                logger.info(f"Token exchange successful. Token expires at {self.token_expires_at}")

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"Token exchange error: {str(e)}")
            raise AgiloftAuthError(f"Token exchange failed: {str(e)}")

    async def _refresh_access_token(self):
        """Refresh the access token using the stored refresh token.

        Uses the refresh_token grant type to obtain a new access token
        without requiring browser-based re-authentication.

        Raises:
            AgiloftAuthError: If the refresh token is missing or the refresh request fails.
        """
        if not self.refresh_token:
            raise AgiloftAuthError("No refresh token available for token refresh")

        await self.ensure_session()

        # Determine token endpoint URL
        if self.oauth2_token_endpoint:
            token_url = self.oauth2_token_endpoint
        elif self.api_access_point:
            token_url = f"{self.api_access_point}/ewws/otoken"
        else:
            base_url = self.base_url.split('/ewws/alrest')[0]
            token_url = f"{base_url}/ewws/otoken"

        logger.info(f"Refreshing access token via {token_url}...")

        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.oauth2_client_id,
            'redirect_uri': self.oauth2_redirect_uri
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

        try:
            async with self.session.post(
                token_url,
                data=token_data,
                headers=headers
            ) as response:
                response_text = await response.text()

                if response.status != 200:
                    error_msg = f"Token refresh failed: {response.status} - {response_text}"
                    logger.error(error_msg)
                    raise AgiloftAuthError(error_msg)

                # Check if response is JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.error(f"Unexpected content type on refresh: {content_type}")
                    raise AgiloftAuthError(
                        f"Expected JSON response but got {content_type}. "
                        f"Response: {response_text[:500]}"
                    )

                data = json.loads(response_text)

                # Extract new access token
                new_access_token = data.get('access_token')
                if not new_access_token:
                    error_msg = f"No access token in refresh response: {data}"
                    logger.error(error_msg)
                    raise AgiloftAuthError(error_msg)

                self.access_token = new_access_token

                # Token expiration (expires_in is in seconds)
                expires_in = data.get('expires_in', 900)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                # Update refresh token if a new one is provided (rotation)
                new_refresh_token = data.get('refresh_token')
                if new_refresh_token:
                    self.refresh_token = new_refresh_token

                logger.info(f"Token refresh successful. New token expires at {self.token_expires_at}")

        except AgiloftAuthError:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise AgiloftAuthError(f"Token refresh failed: {str(e)}")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if not self.access_token:
            raise AgiloftAuthError("No access token available")
            
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the Agiloft API."""
        await self.ensure_authenticated()
        await self.ensure_session()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()

        # Add language parameter if not already present
        params = kwargs.get('params', {})
        if 'lang' not in params:
            params['lang'] = self.language
            kwargs['params'] = params

        # Merge headers
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
        kwargs['headers'] = headers

        # Snapshot current token to detect concurrent refresh by another coroutine
        token_before_request = self.access_token

        logger.debug(f"{method.upper()} {url}")

        try:
            async with self.session.request(method, url, **kwargs) as response:
                response_text = await response.text()
                response_headers = dict(response.headers)

                if response.status == 401:
                    # Token expired — acquire lock to prevent concurrent refresh races.
                    # Without the lock, two concurrent 401s could both attempt refresh,
                    # and with token rotation the second refresh would use an invalidated token.
                    logger.warning(f"Received 401 for {method} {url}, attempting token refresh...")
                    async with self._auth_lock:
                        if self.access_token != token_before_request:
                            # Another concurrent request already refreshed the token
                            logger.info("Token already refreshed by concurrent request, retrying")
                        elif self.refresh_token:
                            try:
                                await self._refresh_access_token()
                            except AgiloftAuthError as e:
                                logger.warning(f"Token refresh failed on 401 retry, falling back to _authenticate: {e}")
                                self.refresh_token = None
                                await self._authenticate()
                        else:
                            await self._authenticate()

                    # Retry the request with new token
                    kwargs['headers'] = self._get_auth_headers()
                    async with self.session.request(method, url, **kwargs) as retry_response:
                        response_text = await retry_response.text()
                        response_headers = dict(retry_response.headers)
                        if retry_response.status not in (200, 201, 202, 204):
                            error_msg = f"API request failed after re-auth: {retry_response.status} - {response_text}"
                            logger.error(f"{error_msg} (URL: {url}, Headers: {response_headers})")
                            raise AgiloftAPIError(
                                error_msg,
                                status_code=retry_response.status,
                                response_text=response_text
                            )
                        if retry_response.status == 204:
                            return {}
                        return await retry_response.json()

                elif response.status not in (200, 201, 202, 204):
                    error_msg = f"API request failed: {response.status} - {response_text}"
                    logger.error(f"{error_msg} (URL: {url}, Method: {method}, Headers: {response_headers})")
                    raise AgiloftAPIError(
                        error_msg,
                        status_code=response.status,
                        response_text=response_text
                    )

                if response.status == 204:
                    return {}
                return await response.json()
                
        except aiohttp.ClientError as e:
            error_msg = f"HTTP client error for {method} {url}: {str(e)}"
            logger.error(error_msg)
            raise AgiloftAPIError(error_msg)
            
    # Contract API Methods
    
    async def search_contracts(self, query: str = "", fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search for contracts."""
        search_data = {
            "search": "",
            "field": fields or [
                "id", "record_type", "contract_title1", "company_name", "date_created",
                "date_submitted", "date_signed", "contract_amount", "contract_end_date",
                "contract_term_in_months", "internal_contract_owner"
            ],
            "query": query
        }
        
        response = await self._make_request("POST", "/contract/search", json=search_data)
        
        if not response.get('success', False):
            raise AgiloftAPIError(f"Search failed: {response.get('message', 'Unknown error')}")
            
        return response.get('result', [])
        
    async def get_contract(self, contract_id: int, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get a specific contract by ID."""
        params = {}
        if fields:
            # Note: The API doesn't seem to support field filtering on GET, but we'll include it for completeness
            params['fields'] = ','.join(fields)
        
        endpoint = f"/contract/{contract_id}"
        logger.debug(f"Getting contract with endpoint: {endpoint}")
        
        response = await self._make_request("GET", endpoint, params=params)
        
        logger.debug(f"Get contract response keys: {list(response.keys())}")
        logger.debug(f"Get contract response: {response}")
        
        # Check multiple possible response formats
        if 'result' in response:
            # Standard Agiloft API format with result key
            contract = response['result']
        elif 'contract' in response:
            # Alternative format with contract key
            contract = response['contract']
        elif isinstance(response, dict) and 'id' in response:
            # Sometimes the response is the contract directly
            contract = response
        elif isinstance(response, list) and len(response) > 0:
            # Sometimes the response is a list with one contract
            contract = response[0]
        else:
            logger.error(f"Unexpected response format for contract {contract_id}: {response}")
            raise AgiloftAPIError(f"Contract not found in response. Response keys: {list(response.keys()) if isinstance(response, dict) else type(response)}")
            
        # If specific fields requested, filter the response
        if fields:
            filtered_contract = {}
            for field in fields:
                if field in contract:
                    filtered_contract[field] = contract[field]
            return filtered_contract
            
        return contract
            
    async def create_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contract."""
        response = await self._make_request("POST", "/contract", json=contract_data)
        
        if not response.get('success', True):  # Some endpoints may not have success field
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Create failed: {error_msg}")
            
        return response
        
    async def update_contract(self, contract_id: int, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing contract."""
        response = await self._make_request("PUT", f"/contract/{contract_id}", json=contract_data)
        
        if not response.get('success', True):
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Update failed: {error_msg}")
            
        return response
        
    async def delete_contract(self, contract_id: int, delete_rule: str = "UNLINK_WHERE_POSSIBLE_OTHERWISE_DELETE") -> Dict[str, Any]:
        """Delete a contract."""
        params = {
            "deleteRule": delete_rule
        }
        
        response = await self._make_request("DELETE", f"/contract/{contract_id}", params=params)
        
        if not response.get('success', False):
            error_msg = response.get('message', 'Unknown error')
            errors = response.get('errors', [])
            if errors:
                error_details = "; ".join([error.get('message', str(error)) for error in errors])
                error_msg += f" - {error_details}"
            raise AgiloftAPIError(f"Delete failed: {error_msg}")
            
        return response
        
    # Utility methods
    
    async def logout(self):
        """Logout and invalidate tokens."""
        if self.access_token:
            try:
                await self._make_request("POST", "/logout")
                logger.info("Logged out successfully")
            except Exception as e:
                logger.warning(f"Logout failed: {str(e)}")
            finally:
                self.access_token = None
                self.refresh_token = None
                self.token_expires_at = None
                self.api_access_point = None