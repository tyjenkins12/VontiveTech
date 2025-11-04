"""CLI entry point for the tax certificate extraction agent."""
import typer
import json
from pathlib import Path
from loguru import logger

from src.utils.logging_config import configure_logging
from src.agent.graph import run_extraction_agent
from src.tools.dataset_tools import get_all_property_ids, search_properties
from src.state import AgentState

app = typer.Typer(
    name="tax-cert-agent",
    help="AI agent for extracting structured data from property tax documents"
)


def _extract_property_id(filename: str) -> str:
    """
    Extract the numeric property ID from a filename.

    Handles filenames like:
    - TaxCertificatesSupportingDocuments_23d65543-1925-45fe-877d-fd60fb1cd529_1760629325007.zip
    - TaxCertificatesSupportingDocuments_23d65543-1925-45fe-877d-fd60fb1cd529_1760629325007
    - 1760629325007.zip
    - 1760629325007

    Returns just the numeric ID: 1760629325007
    """
    # Remove .zip extension if present
    name = filename.replace('.zip', '')

    # If the name contains underscores, take the last part
    if '_' in name:
        return name.split('_')[-1]

    # Otherwise, return as-is (already simplified)
    return name


def _get_user_visible_dataset(dataset: dict) -> dict:
    """
    Filter dataset to only user-visible fields.

    Internal fields like propertyAddress are used for search but not shown to users.
    Only the 7 official schema fields are displayed.
    """
    # Official schema fields (user-visible)
    visible_fields = [
        "taxYear",
        "annualizedAmountDue",
        "amountDueAtClosing",
        "nextTaxPaymentDate",
        "followingTaxPaymentDate",
        "county",
        "parcelNumber"
    ]

    return {k: v for k, v in dataset.items() if k in visible_fields}


def display_results(property_id: str, final_state: AgentState, show_dataset: bool = True) -> None:
    """Display extraction results in a clean format."""
    typer.echo("\n" + "="*60)
    typer.echo(f"PROPERTY: {property_id}")
    typer.echo("="*60)

    # Show dataset (filtered to user-visible fields only)
    if show_dataset:
        dataset = final_state['final_dataset']
        visible_dataset = _get_user_visible_dataset(dataset)
        typer.echo("\n Extracted Data:")
        typer.echo(json.dumps(visible_dataset, indent=2))

    # Show validation errors if any
    if final_state['validation_issues']:
        typer.echo("\n  Validation Warnings:")
        for issue in final_state['validation_issues']:
            typer.echo(f"  • {issue['message']}")
    else:
        typer.echo("\n No validation issues")

    # Show processing info
    typer.echo("\n Processing Info:")
    typer.echo(f"  • Documents: {len(final_state['new_documents'])}")
    if final_state['extraction_method']:
        method_emoji = "" if final_state['extraction_method'] == 'text' else ""
        typer.echo(f"  • Method: {method_emoji} {final_state['extraction_method']}-based extraction")

    output_path = Path("output") / "datasets" / f"{property_id}.json"
    typer.echo(f"  • Saved to: {output_path}")


@app.command()
def extract(
    property_name: str | None = typer.Option(None, "--name", "-n", help="Property name/ID"),
    zip_file: Path | None = typer.Option(None, "--zip", "-z", help="Path to property zip file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed processing logs"),
    log_file: str | None = typer.Option(None, "--log-file", help="Save logs to file"),
) -> None:
    """Extract tax data from property documents (interactive mode)."""

    # Configure logging - suppress console unless verbose
    log_level = "INFO" if verbose else "ERROR"
    configure_logging(level=log_level, log_file=log_file)

    # Interactive mode: prompt for property name if not provided
    if not property_name and not zip_file:
        typer.echo(" Property Tax Certificate Extractor\n")
        property_name = typer.prompt("Enter property name")

        # Auto-find zip file
        tax_certs_dir = Path("tax_certificates")
        if tax_certs_dir.exists():
            matching_files = list(tax_certs_dir.glob(f"*{property_name}*.zip"))
            if matching_files:
                zip_file = matching_files[0]
                typer.echo(f" Found: {zip_file.name}\n")
            else:
                zip_file = Path(typer.prompt("Enter path to zip file"))
        else:
            zip_file = Path(typer.prompt("Enter path to zip file"))

    # If only property name provided, try to find zip file
    if property_name and not zip_file:
        tax_certs_dir = Path("tax_certificates")
        if tax_certs_dir.exists():
            matching_files = list(tax_certs_dir.glob(f"*{property_name}*.zip"))
            if matching_files:
                zip_file = matching_files[0]
                typer.echo(f" Found: {zip_file.name}")
            else:
                typer.echo(f" No zip file found matching '{property_name}' in tax_certificates/", err=True)
                raise typer.Exit(1)
        else:
            typer.echo(" Error: Provide --zip option or create tax_certificates/ directory", err=True)
            raise typer.Exit(1)

    # If only zip file provided, extract ID from filename
    if zip_file and not property_name:
        property_name = zip_file.stem

    # Validate zip file exists
    if not zip_file.exists():
        typer.echo(f" Error: Zip file not found: {zip_file}", err=True)
        raise typer.Exit(1)

    # Extract simplified property ID
    property_id = _extract_property_id(property_name)

    typer.echo(" Processing...\n")

    try:
        # Run the agent
        final_state = run_extraction_agent(
            property_id=property_id,
            zip_file_path=str(zip_file)
        )

        # Display clean results
        display_results(property_id, final_state)

    except Exception as e:
        logger.exception("Processing failed")
        typer.echo(f"\n Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def process(
    zip_file: Path = typer.Argument(..., help="Path to property zip file"),
    property_id: str | None = typer.Option(None, help="Property ID (defaults to zip filename)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed processing logs"),
    log_file: str | None = typer.Option(None, help="Optional log file path"),
) -> None:
    """Process a single property's tax certificates (non-interactive)."""

    # Configure logging - suppress console unless verbose
    log_level = "INFO" if verbose else "ERROR"
    configure_logging(level=log_level, log_file=log_file)

    # Validate zip file exists
    if not zip_file.exists():
        typer.echo(f" Error: Zip file not found: {zip_file}", err=True)
        raise typer.Exit(1)

    # Determine property ID and extract simplified ID
    if not property_id:
        property_id = zip_file.stem
    property_id = _extract_property_id(property_id)

    typer.echo(" Processing...\n")

    try:
        # Run the agent
        final_state = run_extraction_agent(
            property_id=property_id,
            zip_file_path=str(zip_file)
        )

        # Display clean results
        display_results(property_id, final_state)

    except Exception as e:
        logger.exception("Processing failed")
        typer.echo(f"\n Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def batch(
    input_dir: Path = typer.Option("tax_certificates", help="Directory with zip files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed processing logs"),
    log_file: str | None = typer.Option(None, help="Optional log file path"),
) -> None:
    """Process all properties in a directory."""

    # Configure logging - suppress console unless verbose
    log_level = "INFO" if verbose else "ERROR"
    configure_logging(level=log_level, log_file=log_file)

    # Validate input directory
    if not input_dir.exists() or not input_dir.is_dir():
        typer.echo(f" Error: Input directory not found: {input_dir}", err=True)
        raise typer.Exit(1)

    # Find all zip files
    zip_files = list(input_dir.glob("*.zip"))

    if not zip_files:
        typer.echo(f" Error: No zip files found in {input_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f" Processing {len(zip_files)} properties...\n")

    # Process each property
    results = []
    for i, zip_file in enumerate(zip_files, 1):
        # Extract simplified property ID from filename
        property_id = _extract_property_id(zip_file.stem)

        typer.echo(f"[{i}/{len(zip_files)}] {property_id}...", nl=False)

        try:
            final_state = run_extraction_agent(
                property_id=property_id,
                zip_file_path=str(zip_file)
            )

            results.append({
                "property_id": property_id,
                "status": "success",
                "validation_issues": len(final_state['validation_issues']),
                "extraction_method": final_state['extraction_method'],
                "doc_count": len(final_state['new_documents'])
            })

            typer.echo(f" ")

        except Exception as e:
            logger.error(f"Failed to process {property_id}: {e}")
            results.append({
                "property_id": property_id,
                "status": "failed",
                "error": str(e)
            })
            typer.echo(f"  {e}")

    # Summary
    typer.echo("\n" + "="*60)
    typer.echo("BATCH PROCESSING SUMMARY")
    typer.echo("="*60)

    successful = sum(1 for r in results if r['status'] == 'success')
    failed = sum(1 for r in results if r['status'] == 'failed')

    typer.echo(f"\nTotal properties: {len(results)}")
    typer.echo(f"   Successful: {successful}")
    typer.echo(f"   Failed: {failed}")

    # Show extraction method breakdown
    if successful > 0:
        text_count = sum(1 for r in results if r.get('extraction_method') == 'text')
        vision_count = sum(1 for r in results if r.get('extraction_method') == 'vision')

        typer.echo(f"\nExtraction methods:")
        typer.echo(f"   Text-only: {text_count}")
        typer.echo(f"   Vision: {vision_count}")

        if text_count > 0:
            savings_pct = (text_count / successful) * 100
            typer.echo(f"   Cost savings: ~{savings_pct:.1f}% used cheaper text extraction")

    output_dir = Path("output") / "datasets"
    typer.echo(f"\n Datasets saved to: {output_dir}")


@app.command()
def list_properties() -> None:
    """List all properties that have been processed."""
    property_ids = get_all_property_ids()

    if not property_ids:
        typer.echo("No properties found in output directory.")
        return

    typer.echo(f"Found {len(property_ids)} processed propert{'y' if len(property_ids) == 1 else 'ies'}:")
    for prop_id in property_ids:
        typer.echo(f"  • {prop_id}")


@app.command()
def search(
    address: str | None = typer.Option(None, "--address", "-a", help="Search by property address (partial match)"),
    parcel: str | None = typer.Option(None, "--parcel", "-p", help="Search by parcel number (partial match)"),
    county: str | None = typer.Option(None, "--county", "-c", help="Search by county name (partial match)"),
    year: str | None = typer.Option(None, "--year", "-y", help="Search by tax year (exact match)"),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json, table, csv"),
    fuzzy: bool = typer.Option(False, "--fuzzy", help="Enable fuzzy matching for approximate searches"),
    fuzzy_threshold: float = typer.Option(0.6, "--fuzzy-threshold", help="Fuzzy match threshold (0.0-1.0, default: 0.6)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Enable interactive property selection"),
) -> None:
    """Search properties by address, parcel number, county, or tax year."""

    # At least one search criterion required
    if not any([address, parcel, county, year]):
        typer.echo(" Error: Provide at least one search criterion", err=True)
        typer.echo("\nExamples:")
        typer.echo("  python -m src.main search --address 'Main Street'")
        typer.echo("  python -m src.main search --parcel '210-691'")
        typer.echo("  python -m src.main search --county 'Contra Costa' --year 2025")
        typer.echo("  python -m src.main search --county 'Contra' --fuzzy")
        typer.echo("  python -m src.main search --address 'Main Street' --interactive")
        raise typer.Exit(1)

    # Perform search
    results = search_properties(
        address=address,
        parcel=parcel,
        county=county,
        tax_year=year,
        fuzzy=fuzzy,
        fuzzy_threshold=fuzzy_threshold
    )

    # Handle no results
    if not results:
        typer.echo("No properties found matching the search criteria.")
        return

    # Interactive mode - let user select a property
    if interactive:
        _interactive_property_selection(results)
        return

    # Display results based on format
    if output_format.lower() == "json":
        _display_search_json(results)
    elif output_format.lower() == "table":
        _display_search_table(results)
    elif output_format.lower() == "csv":
        _display_search_csv(results)
    else:
        typer.echo(f" Error: Unknown format '{output_format}'. Use: json, table, csv", err=True)
        raise typer.Exit(1)


def _display_search_json(results: list[tuple[str, dict]]) -> None:
    """Display search results in JSON format."""
    typer.echo(f"\n Found {len(results)} matching propert{'y' if len(results) == 1 else 'ies'}:\n")

    output = []
    for property_id, dataset in results:
        # Filter to user-visible fields only
        visible_dataset = _get_user_visible_dataset(dataset)
        output.append({
            "property_id": property_id,
            "dataset": visible_dataset
        })

    typer.echo(json.dumps(output, indent=2))


def _display_search_table(results: list[tuple[str, dict]]) -> None:
    """Display search results in table format."""
    typer.echo(f"\n Found {len(results)} matching propert{'y' if len(results) == 1 else 'ies'}:\n")

    # Header
    typer.echo("─" * 120)
    typer.echo(f"{'Property ID':<25} {'Address':<35} {'Parcel':<20} {'County':<15} {'Year':<5}")
    typer.echo("─" * 120)

    # Rows
    for property_id, dataset in results:
        address = dataset.get('propertyAddress', 'N/A')
        parcel = dataset.get('parcelNumber', 'N/A')
        county = dataset.get('county', 'N/A')
        year = dataset.get('taxYear', 'N/A')

        # Truncate long values
        if len(str(address)) > 33:
            address = str(address)[:30] + "..."
        if len(str(property_id)) > 23:
            property_id = property_id[:20] + "..."

        typer.echo(f"{property_id:<25} {address:<35} {parcel:<20} {county:<15} {year:<5}")

    typer.echo("─" * 120)


def _display_search_csv(results: list[tuple[str, dict]]) -> None:
    """Display search results in CSV format."""
    import csv
    import sys

    writer = csv.writer(sys.stdout)

    # Header
    writer.writerow([
        'property_id',
        'tax_year',
        'annualized_amount_due',
        'amount_due_at_closing',
        'county',
        'parcel_number',
        'next_tax_payment_date',
        'following_tax_payment_date',
        'property_address'
    ])

    # Rows
    for property_id, dataset in results:
        writer.writerow([
            property_id,
            dataset.get('taxYear', ''),
            dataset.get('annualizedAmountDue', ''),
            dataset.get('amountDueAtClosing', ''),
            dataset.get('county', ''),
            dataset.get('parcelNumber', ''),
            dataset.get('nextTaxPaymentDate', ''),
            dataset.get('followingTaxPaymentDate', ''),
            dataset.get('propertyAddress', '')
        ])


def _interactive_property_selection(results: list[tuple[str, dict]]) -> None:
    """Interactive property selection from search results."""
    typer.echo(f"\n Found {len(results)} matching propert{'y' if len(results) == 1 else 'ies'}:\n")

    # Display numbered list with summary info
    for i, (property_id, dataset) in enumerate(results, 1):
        address = dataset.get('propertyAddress', 'N/A')
        parcel = dataset.get('parcelNumber', 'N/A')
        county = dataset.get('county', 'N/A')
        year = dataset.get('taxYear', 'N/A')

        typer.echo(f"{i}. {property_id}")
        typer.echo(f"   Address: {address}")
        typer.echo(f"   Parcel: {parcel}, County: {county}, Year: {year}")
        typer.echo()

    # Prompt for selection
    while True:
        selection = typer.prompt(
            f"Select property (1-{len(results)}) or 'q' to quit",
            type=str
        )

        if selection.lower() == 'q':
            typer.echo("Exited.")
            return

        try:
            index = int(selection) - 1
            if 0 <= index < len(results):
                property_id, dataset = results[index]
                _display_property_details(property_id, dataset)

                # Ask if user wants to export or select another
                action = typer.prompt(
                    "\nActions: [e]xport to CSV, [s]elect another, [q]uit",
                    type=str,
                    default="q"
                )

                if action.lower() == 'e':
                    _export_property_to_csv(property_id, dataset)
                elif action.lower() == 's':
                    continue
                else:
                    return
            else:
                typer.echo(f" Invalid selection. Choose 1-{len(results)}", err=True)
        except ValueError:
            typer.echo(" Invalid input. Enter a number or 'q'", err=True)


def _display_property_details(property_id: str, dataset: dict) -> None:
    """Display detailed information about a single property."""
    typer.echo("\n" + "="*60)
    typer.echo(f"PROPERTY DETAILS: {property_id}")
    typer.echo("="*60)
    typer.echo("\n Full Dataset:")
    # Filter to user-visible fields only
    visible_dataset = _get_user_visible_dataset(dataset)
    typer.echo(json.dumps(visible_dataset, indent=2))


def _export_property_to_csv(property_id: str, dataset: dict) -> None:
    """Export a single property to CSV file."""
    import csv

    output_file = Path(f"{property_id}.csv")

    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'property_id',
                'tax_year',
                'annualized_amount_due',
                'amount_due_at_closing',
                'county',
                'parcel_number',
                'next_tax_payment_date',
                'following_tax_payment_date',
                'property_address'
            ])

            # Row
            writer.writerow([
                property_id,
                dataset.get('taxYear', ''),
                dataset.get('annualizedAmountDue', ''),
                dataset.get('amountDueAtClosing', ''),
                dataset.get('county', ''),
                dataset.get('parcelNumber', ''),
                dataset.get('nextTaxPaymentDate', ''),
                dataset.get('followingTaxPaymentDate', ''),
                dataset.get('propertyAddress', '')
            ])

        typer.echo(f"\n Exported to: {output_file}")

    except Exception as e:
        typer.echo(f"\n Export failed: {e}", err=True)


if __name__ == "__main__":
    app()
