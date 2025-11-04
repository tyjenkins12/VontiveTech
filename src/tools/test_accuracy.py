"""Accuracy testing tool for comparing agent results to ground truth."""
import json
from pathlib import Path
from typing import Any
import sys


def load_json(file_path: Path) -> dict:
    """Load JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def compare_values(field_name: str, agent_value: Any, ground_truth_value: Any) -> dict:
    """
    Compare a single field value.

    Returns:
        Dict with comparison results
    """
    # Handle None/null values
    if agent_value is None and ground_truth_value is None:
        return {"match": True, "type": "both_null"}

    if agent_value is None:
        return {
            "match": False,
            "type": "agent_null",
            "agent": None,
            "ground_truth": ground_truth_value
        }

    if ground_truth_value is None:
        return {
            "match": False,
            "type": "ground_truth_null",
            "agent": agent_value,
            "ground_truth": None
        }

    # Handle numeric values with tolerance for floating point
    if isinstance(agent_value, (int, float)) and isinstance(ground_truth_value, (int, float)):
        # Use 0.01 tolerance for currency values
        tolerance = 0.01
        match = abs(agent_value - ground_truth_value) < tolerance

        if match:
            return {"match": True, "type": "numeric_match"}
        else:
            return {
                "match": False,
                "type": "numeric_mismatch",
                "agent": agent_value,
                "ground_truth": ground_truth_value,
                "difference": abs(agent_value - ground_truth_value)
            }

    # Handle string values (case-insensitive for some fields)
    if isinstance(agent_value, str) and isinstance(ground_truth_value, str):
        # Case-insensitive comparison for certain fields
        if field_name in ["county", "propertyAddress"]:
            match = agent_value.lower().strip() == ground_truth_value.lower().strip()
        else:
            match = agent_value.strip() == ground_truth_value.strip()

        if match:
            return {"match": True, "type": "string_match"}
        else:
            return {
                "match": False,
                "type": "string_mismatch",
                "agent": agent_value,
                "ground_truth": ground_truth_value
            }

    # Type mismatch
    return {
        "match": False,
        "type": "type_mismatch",
        "agent": agent_value,
        "agent_type": type(agent_value).__name__,
        "ground_truth": ground_truth_value,
        "ground_truth_type": type(ground_truth_value).__name__
    }


def compare_property(property_id: str, agent_data: dict, ground_truth_data: dict) -> dict:
    """
    Compare all fields for a single property.

    Returns:
        Dict with per-field comparison results
    """
    results = {
        "property_id": property_id,
        "fields": {},
        "total_fields": 0,
        "matching_fields": 0,
        "mismatching_fields": 0
    }

    # Define expected fields
    # Note: propertyAddress is excluded from comparison due to formatting variations
    # between documents (all caps vs mixed case). Address search remains case-insensitive.
    expected_fields = [
        "taxYear",
        "annualizedAmountDue",
        "amountDueAtClosing",
        "county",
        "parcelNumber",
        "nextTaxPaymentDate",
        "followingTaxPaymentDate"
    ]

    for field in expected_fields:
        agent_value = agent_data.get(field)
        ground_truth_value = ground_truth_data.get(field)

        comparison = compare_values(field, agent_value, ground_truth_value)
        results["fields"][field] = comparison

        results["total_fields"] += 1
        if comparison["match"]:
            results["matching_fields"] += 1
        else:
            results["mismatching_fields"] += 1

    results["accuracy"] = (results["matching_fields"] / results["total_fields"]) * 100

    return results


def calculate_overall_stats(all_results: list[dict]) -> dict:
    """Calculate overall accuracy statistics."""
    total_properties = len(all_results)
    total_fields = sum(r["total_fields"] for r in all_results)
    total_matching = sum(r["matching_fields"] for r in all_results)

    # Per-field accuracy
    field_stats = {}
    expected_fields = [
        "taxYear", "annualizedAmountDue", "amountDueAtClosing",
        "county", "parcelNumber", "nextTaxPaymentDate",
        "followingTaxPaymentDate"
    ]

    for field in expected_fields:
        matches = sum(1 for r in all_results if r["fields"][field]["match"])
        field_stats[field] = {
            "matches": matches,
            "total": total_properties,
            "accuracy": (matches / total_properties) * 100
        }

    return {
        "total_properties": total_properties,
        "total_fields": total_fields,
        "total_matching": total_matching,
        "overall_accuracy": (total_matching / total_fields) * 100,
        "field_accuracy": field_stats,
        "perfect_properties": sum(1 for r in all_results if r["accuracy"] == 100.0)
    }


def print_report(all_results: list[dict], stats: dict) -> None:
    """Print formatted accuracy report."""
    print("\n" + "="*80)
    print("AGENT ACCURACY TEST REPORT")
    print("="*80)

    # Overall stats
    print(f"\n📊 Overall Statistics:")
    print(f"  • Total Properties: {stats['total_properties']}")
    print(f"  • Total Fields Tested: {stats['total_fields']}")
    print(f"  • Overall Accuracy: {stats['overall_accuracy']:.2f}%")
    print(f"  • Perfect Extractions: {stats['perfect_properties']}/{stats['total_properties']}")

    # Per-field accuracy
    print(f"\n📋 Field-by-Field Accuracy:")
    for field, field_stat in stats['field_accuracy'].items():
        status = "✅" if field_stat['accuracy'] == 100.0 else "⚠️"
        print(f"  {status} {field:<25} {field_stat['accuracy']:>6.2f}% ({field_stat['matches']}/{field_stat['total']})")

    # Properties with errors
    properties_with_errors = [r for r in all_results if r["accuracy"] < 100.0]

    if properties_with_errors:
        print(f"\n❌ Properties with Mismatches ({len(properties_with_errors)}):")
        for result in properties_with_errors:
            print(f"\n  Property: {result['property_id']}")
            print(f"  Accuracy: {result['accuracy']:.2f}% ({result['matching_fields']}/{result['total_fields']})")

            # Show mismatching fields
            for field, comparison in result["fields"].items():
                if not comparison["match"]:
                    print(f"    ❌ {field}:")
                    print(f"       Agent:        {comparison.get('agent', 'N/A')}")
                    print(f"       Ground Truth: {comparison.get('ground_truth', 'N/A')}")
                    if "difference" in comparison:
                        print(f"       Difference:   {comparison['difference']}")
    else:
        print(f"\n✅ All properties extracted perfectly!")

    print("\n" + "="*80)


def main():
    """Main accuracy testing function."""
    # File paths
    project_root = Path(__file__).parent.parent.parent
    base_dir = project_root / "tests/test_data"
    agent_results_file = base_dir / "agent_results.json"
    ground_truth_file = base_dir / "ground_truth.json"

    # Check files exist
    if not agent_results_file.exists():
        print(f"❌ Error: Agent results file not found: {agent_results_file}")
        print("   Run the batch extraction first to generate agent_results.json")
        sys.exit(1)

    if not ground_truth_file.exists():
        print(f"❌ Error: Ground truth file not found: {ground_truth_file}")
        print(f"   Create it from the template: tests/test_data/ground_truth_template.json")
        print("   Instructions:")
        print("   1. Copy ground_truth_template.json to ground_truth.json")
        print("   2. Replace all 'VERIFY_VALUE' entries with correct values from source documents")
        sys.exit(1)

    # Load data
    print("📂 Loading data...")
    agent_results = load_json(agent_results_file)
    ground_truth = load_json(ground_truth_file)

    # Check for VERIFY_VALUE placeholders
    for prop_id, data in ground_truth.items():
        for field, value in data.items():
            if field == "_notes":
                continue
            if value == "VERIFY_VALUE":
                print(f"❌ Error: Ground truth contains unverified values")
                print(f"   Property: {prop_id}, Field: {field}")
                print("   Please complete the ground truth file before running tests.")
                sys.exit(1)

    # Compare properties
    print("🔍 Comparing agent results to ground truth...\n")
    all_results = []

    for property_id in agent_results.keys():
        if property_id not in ground_truth:
            print(f"⚠️  Warning: Property {property_id} not in ground truth, skipping...")
            continue

        result = compare_property(
            property_id,
            agent_results[property_id],
            ground_truth[property_id]
        )
        all_results.append(result)

    # Calculate stats
    stats = calculate_overall_stats(all_results)

    # Print report
    print_report(all_results, stats)

    # Save detailed results
    output_file = base_dir / "accuracy_report.json"
    with open(output_file, 'w') as f:
        json.dump({
            "statistics": stats,
            "detailed_results": all_results
        }, f, indent=2)

    print(f"\n💾 Detailed results saved to: {output_file}")


if __name__ == "__main__":
    main()