#!/usr/bin/env python3
"""
OAuth2 Authorization Code Flow Example

This script demonstrates OAuth2 authentication using the Authorization Code flow,
which opens a browser for the user to log in to Agiloft.

Usage:
    python example_oauth2_browser.py

Configuration:
    Set environment variables or use config.json with OAuth2 authorization_code settings.
"""

import asyncio
import logging
from agiloft.config import Config
from agiloft.client import AgiloftClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main example function demonstrating OAuth2 Authorization Code flow."""
    print("=" * 70)
    print("Agiloft API - OAuth2 Authorization Code Flow Example")
    print("=" * 70)
    print()

    # Load configuration
    try:
        config = Config()

        # Verify OAuth2 authorization code is configured
        auth_method = config.get('agiloft.auth_method', 'legacy')
        if auth_method != 'oauth2_authorization_code':
            logger.warning(f"auth_method is set to '{auth_method}', not 'oauth2_authorization_code'")
            logger.info("To use OAuth2 Authorization Code flow, set AGILOFT_AUTH_METHOD=oauth2_authorization_code")
            return

        if not config.validate():
            logger.error("Configuration validation failed.")
            logger.error("Required OAuth2 Authorization Code settings:")
            logger.error("  - AGILOFT_BASE_URL")
            logger.error("  - AGILOFT_KB")
            logger.error("  - AGILOFT_OAUTH2_CLIENT_ID")
            logger.error("  - AGILOFT_OAUTH2_CLIENT_SECRET")
            logger.error("  - AGILOFT_OAUTH2_AUTHORIZATION_ENDPOINT")
            logger.error("  - AGILOFT_OAUTH2_TOKEN_ENDPOINT")
            logger.error("  - AGILOFT_OAUTH2_REDIRECT_URI")
            return

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return

    # Use the Agiloft client with OAuth2 Authorization Code flow
    async with AgiloftClient(config) as client:
        try:
            logger.info("Starting OAuth2 Authorization Code flow...")
            print()
            print("IMPORTANT: Your browser will open for you to log in to Agiloft.")
            print("After logging in, you'll be redirected back to this application.")
            print("Waiting 3 seconds before opening browser...")
            print()

            # Wait a moment so user can read the message
            await asyncio.sleep(3)

            # Authenticate with browser
            await client.authenticate_with_browser()
            print()
            logger.info("✅ OAuth2 authentication successful!")
            print()

            # Example 1: Search for contracts
            logger.info("Example 1: Searching for contracts...")
            contracts = await client.search_contracts(
                query="",
                fields=["id", "contract_title1", "company_name", "contract_amount"]
            )

            logger.info(f"Found {len(contracts)} contracts")
            if contracts:
                print()
                print("Sample contracts:")
                for i, contract in enumerate(contracts[:5], 1):
                    print(f"  {i}. ID: {contract.get('id')}, "
                          f"Title: {contract.get('contract_title1', 'N/A')}, "
                          f"Company: {contract.get('company_name', 'N/A')}")
            print()

            # Example 2: Get a specific contract (if any exist)
            if contracts:
                contract_id = contracts[0].get('id')
                logger.info(f"Example 2: Getting contract details for ID {contract_id}...")
                contract = await client.get_contract(
                    contract_id=contract_id,
                    fields=["id", "contract_title1", "company_name", "date_created"]
                )
                print()
                print(f"Contract Details:")
                print(f"  ID: {contract.get('id')}")
                print(f"  Title: {contract.get('contract_title1', 'N/A')}")
                print(f"  Company: {contract.get('company_name', 'N/A')}")
                print(f"  Created: {contract.get('date_created', 'N/A')}")
                print()

            logger.info("✅ All examples completed successfully!")

        except Exception as e:
            logger.error(f"Error during API operations: {e}")
            import traceback
            traceback.print_exc()
            return

    print("=" * 70)
    print("OAuth2 Authorization Code flow example completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
