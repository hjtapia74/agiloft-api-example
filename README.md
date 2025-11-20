# Agiloft API Example

A simple Python example demonstrating how to interact with Agiloft's REST API. This repository provides a clean, standalone implementation for connecting to Agiloft and exporting contract data to CSV.

## Features

- **Simple Agiloft API Client**: Easy-to-use Python client for Agiloft REST API
- **Automatic Authentication**: Handles Bearer token authentication with automatic refresh
- **CSV Export Tool**: Export all contracts from Agiloft to CSV format
- **Flexible Configuration**: Support for both config files and environment variables
- **Minimal Dependencies**: Only requires `aiohttp`

## Use Cases

This example is perfect for:
- Learning how to integrate with Agiloft's REST API
- Exporting contract data for analysis or reporting
- Building custom integrations with Agiloft
- Data migration or backup tasks

## Installation

### Prerequisites

- Python 3.8 or higher
- Access to an Agiloft instance with REST API enabled
- Agiloft credentials (username, password, knowledge base name)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/hjtapia74/agiloft-api-example.git
cd agiloft-api-example
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your Agiloft credentials (choose one method):

   **Option A: Configuration File** (recommended for development)
   ```bash
   cp example_config.json config.json
   # Edit config.json with your Agiloft credentials
   ```

   **Option B: Environment Variables** (recommended for production)
   ```bash
   export AGILOFT_BASE_URL="https://your-instance.saas.agiloft.com/ewws/alrest/YourKB"
   export AGILOFT_USERNAME="your-username"
   export AGILOFT_PASSWORD="your-password"
   export AGILOFT_KB="YourKB"
   ```

## Usage

### Exporting Contracts to CSV

Run the export script to download all contracts from your Agiloft instance:

```bash
python export_contracts_to_csv.py
```

This will:
1. Authenticate with Agiloft using your credentials
2. Retrieve all contracts from the Contract table
3. Export them to a timestamped CSV file (e.g., `agiloft_contracts_20251120_143052.csv`)

**Output includes fields:**
- Contract ID, title, company name
- Contract amounts and dates
- Record type and internal owner
- All other available contract fields

### Using the API Client in Your Own Code

```python
import asyncio
from agiloft.config import Config
from agiloft.client import AgiloftClient

async def main():
    # Load configuration
    config = Config()

    # Use the client
    async with AgiloftClient(config) as client:
        # Authentication happens automatically

        # Search for contracts
        contracts = await client.search_contracts(
            query="contract_amount>100000",
            fields=["id", "contract_title1", "company_name", "contract_amount"]
        )

        print(f"Found {len(contracts)} contracts")
        for contract in contracts:
            print(f"- {contract['contract_title1']}: ${contract['contract_amount']}")

        # Get a specific contract
        contract = await client.get_contract(contract_id=123)
        print(f"Contract details: {contract}")

        # Create a new contract
        new_contract = await client.create_contract({
            "contract_title1": "New Agreement",
            "company_name": "Acme Corp",
            "contract_amount": 50000
        })

        # Update a contract
        await client.update_contract(123, {
            "contract_amount": 60000
        })

        # Delete a contract
        await client.delete_contract(123)

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

Configuration priority: **Environment Variables > config.json > defaults**

### Required Settings

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| `agiloft.base_url` | `AGILOFT_BASE_URL` | Full REST API endpoint URL |
| `agiloft.username` | `AGILOFT_USERNAME` | Your Agiloft username |
| `agiloft.password` | `AGILOFT_PASSWORD` | Your Agiloft password |
| `agiloft.kb` | `AGILOFT_KB` | Knowledge base name |

### Optional Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `agiloft.language` | `AGILOFT_LANGUAGE` | `en` | Language code |

### Example config.json

```json
{
  "agiloft": {
    "base_url": "https://your-instance.saas.agiloft.com/ewws/alrest/YourKB",
    "username": "admin",
    "password": "your-password",
    "kb": "YourKB",
    "language": "en"
  }
}
```

**Security Note:** Never commit `config.json` to version control. Use environment variables for production deployments.

## Project Structure

```
agiloft-api-example/
├── agiloft/                    # Agiloft API client library
│   ├── __init__.py
│   ├── client.py              # AgiloftClient - main API client
│   ├── config.py              # Config - configuration manager
│   └── exceptions.py          # Custom exception classes
├── export_contracts_to_csv.py # Example: Export contracts to CSV
├── example_config.json        # Configuration template
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## API Client Features

### AgiloftClient

The `AgiloftClient` class provides methods for interacting with Agiloft's REST API:

**Contract Operations:**
- `search_contracts(query, fields, limit)` - Search for contracts
- `get_contract(contract_id, fields)` - Get a specific contract
- `create_contract(contract_data)` - Create a new contract
- `update_contract(contract_id, contract_data)` - Update a contract
- `delete_contract(contract_id, delete_rule)` - Delete a contract

**Authentication:**
- Automatic token management with 15-minute expiration
- Proactive token refresh (1 minute before expiration)
- Automatic retry on 401 errors
- Thread-safe authentication with async locks

**Error Handling:**
- `AgiloftAuthError` - Authentication failures
- `AgiloftAPIError` - API request/response errors
- `AgiloftConfigError` - Configuration issues

## Customization

### Modify Export Fields

Edit `export_contracts_to_csv.py` to change which fields are exported:

```python
contracts = await client.search_contracts(
    query="",
    fields=[
        "id", "contract_title1", "company_name",
        # Add or remove fields here
        "your_custom_field"
    ]
)
```

### Filter Contracts

Add a query to export only specific contracts:

```python
# Export only active contracts
contracts = await client.search_contracts(
    query="status=Active",
    fields=[...]
)

# Export contracts by date range
contracts = await client.search_contracts(
    query="date_signed>='2024-01-01'",
    fields=[...]
)
```

## Error Handling

The client provides detailed error messages with context:

```python
try:
    contract = await client.get_contract(123)
except AgiloftAuthError as e:
    print(f"Authentication failed: {e}")
except AgiloftAPIError as e:
    print(f"API error: {e}")
    print(f"Status code: {e.status_code}")
    print(f"Response: {e.response_text}")
```

## Best Practices

1. **Use Environment Variables in Production**: Never hardcode credentials
2. **Implement Retry Logic**: Handle transient network errors
3. **Respect Rate Limits**: Agiloft may have API rate limits
4. **Validate Field Names**: Field names vary between Agiloft instances
5. **Log Appropriately**: Use logging for debugging, not print statements

## Troubleshooting

### Authentication Errors

- Verify your credentials are correct
- Check that the base URL includes the full REST API path
- Ensure your Agiloft user has API access permissions

### Missing Fields

If you get "No column=field_name" errors:
- The field doesn't exist in your Agiloft schema
- Remove the field from your query or use a different field name
- Check your Agiloft instance for available field names

### Token Expiration

The client automatically handles token refresh, but if you see token errors:
- Check your system clock is synchronized
- Verify network connectivity to Agiloft
- Check Agiloft logs for token issues

## Contributing

Contributions are welcome! This is an example project to help developers learn Agiloft API integration.

## License

[Add your license here]

## Support

For questions or issues:
- Open an issue on GitHub
- Review Agiloft's REST API documentation
- Check the example code in this repository

## Acknowledgments

Built with:
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client/server
- [Agiloft REST API](https://agiloft.com/)
