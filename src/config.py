"""Configuration for the tax certificate extraction agent."""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Model Configuration
MODEL = "claude-sonnet-4-5"  # Claude Sonnet 4.5
MAX_TOKENS = 2048
TEMPERATURE = 0

# Internal schema (includes hidden fields for search)
# Note: propertyAddress is extracted and stored but NOT shown to users
# Only the 7 official fields from tax_certificate_schema.json are user-visible
DATASET_SCHEMA = {
    "type": "object",
    "properties": {
        "taxYear": {"type": "string"},
        "annualizedAmountDue": {"type": "number"},
        "amountDueAtClosing": {"type": "number"},
        "nextTaxPaymentDate": {"type": "string", "format": "date"},
        "followingTaxPaymentDate": {"type": "string", "format": "date"},
        "county": {"type": "string"},
        "parcelNumber": {"type": "string"},
        "propertyAddress": {"type": "string"}  # INTERNAL ONLY - for search, not displayed to users
    },
    "required": [
        "taxYear",
        "annualizedAmountDue",
        "amountDueAtClosing",
        "nextTaxPaymentDate",
        "followingTaxPaymentDate",
        "county",
        "parcelNumber"
    ]
}
