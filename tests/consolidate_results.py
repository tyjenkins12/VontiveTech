import json
from pathlib import Path

# Get project root (parent of tests directory)
project_root = Path(__file__).parent.parent

# Read all dataset files
datasets_dir = project_root / "output/datasets"
all_results = {}

for json_file in sorted(datasets_dir.glob("*.json")):
    # Skip backup files
    if json_file.name.endswith(".backup"):
        continue

    property_id = json_file.stem

    with open(json_file, 'r') as f:
        dataset = json.load(f)

    all_results[property_id] = dataset

# Write consolidated results
output_file = project_root / "tests/test_data/agent_results.json"
output_file.parent.mkdir(exist_ok=True)

with open(output_file, 'w') as f:
    json.dump(all_results, f, indent=2)

print(f" Consolidated {len(all_results)} property results to {output_file}")
print(f"\nProperties included:")
for prop_id in sorted(all_results.keys()):
    print(f"  • {prop_id}")
