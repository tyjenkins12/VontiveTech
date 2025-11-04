import json
from pathlib import Path

# Get project root (parent of tests directory)
project_root = Path(__file__).parent.parent

# Read agent results to get property IDs
agent_results_file = project_root / "tests/test_data/agent_results.json"
with open(agent_results_file, 'r') as f:
    agent_results = json.load(f)

# Create ground truth template with same structure
ground_truth_template = {}

for property_id, agent_data in agent_results.items():
    ground_truth_template[property_id] = {
        "taxYear": agent_data.get("taxYear", "VERIFY_VALUE"),
        "annualizedAmountDue": agent_data.get("annualizedAmountDue", "VERIFY_VALUE"),
        "amountDueAtClosing": agent_data.get("amountDueAtClosing", "VERIFY_VALUE"),
        "county": agent_data.get("county", "VERIFY_VALUE"),
        "parcelNumber": agent_data.get("parcelNumber", "VERIFY_VALUE"),
        "nextTaxPaymentDate": agent_data.get("nextTaxPaymentDate", "VERIFY_VALUE"),
        "followingTaxPaymentDate": agent_data.get("followingTaxPaymentDate", "VERIFY_VALUE"),
        "propertyAddress": agent_data.get("propertyAddress", "VERIFY_VALUE"),
        "_notes": "Manually verify and update all VERIFY_VALUE entries with ground truth"
    }

# Write ground truth template
output_file = project_root / "tests/test_data/ground_truth_template.json"
with open(output_file, 'w') as f:
    json.dump(ground_truth_template, f, indent=2)

print(f" Created ground truth template: {output_file}")
print(f"\nNext steps:")
print("1. Review each property's source documents")
print("2. Replace all 'VERIFY_VALUE' placeholders with actual correct values")
print("3. Save as tests/test_data/ground_truth.json")
print("4. Run: python src/tools/test_accuracy.py")
