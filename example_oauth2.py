#!/usr/bin/env python3
"""
OAuth2 Authentication Example

This script demonstrates how to use OAuth2 client credentials
authentication with the Agiloft API client.

Usage:
    python example_oauth2.py

Configuration:
    Set environment variables or use config.json with OAuth2 credentials.
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
    """Main example function demonstrating OAuth2 usage."""
    print("=" * 60)
    print("Agiloft API - OAuth2 Authentication Example")
    print("=" * 60)
    print()

    # Load configuration
    try:
        config = Config()

        # Verify OAuth2 is configured
        auth_method = config.get('agiloft.auth_method', 'legacy')
        if auth_method != 'oauth2':
            logger.warning("auth_method is set to '%s', not 'oauth2'", auth_method)
            logger.info("To use OAuth2, set AGILOFT_AUTH_METHOD=oauth2 or update config.json")
            return

        if not config.validate():
            logger.error("Configuration validation failed.")
            logger.error("Required OAuth2 settings:")
            logger.error("  - AGILOFT_BASE_URL")
            logger.error("  - AGILOFT_KB")
            logger.error("  - AGILOFT_OAUTH2_CLIENT_ID")
            logger.error("  - AGILOFT_OAUTH2_CLIENT_SECRET")
            logger.error("  - AGILOFT_OAUTH2_TOKEN_ENDPOINT")
            return

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return

    # Use the Agiloft client with OAuth2
    async with AgiloftClient(config) as client:
        try:
            logger.info("Authenticating with OAuth2...")
            await client.ensure_authenticated()
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
            return

    print("=" * 60)
    print("OAuth2 authentication example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
