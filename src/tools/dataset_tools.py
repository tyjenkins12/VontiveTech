"""Dataset management and persistence tools."""
import json
from pathlib import Path
from loguru import logger

from src.config import DATASET_SCHEMA
from src.state import PropertyID, DocumentTuple, Dataset


# Storage directory for datasets and documents
STORAGE_DIR = Path("output")
DATASETS_DIR = STORAGE_DIR / "datasets"
DOCUMENTS_DIR = STORAGE_DIR / "documents"


def _ensure_directories():
    """Create storage directories if they don't exist."""
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def get_existing_dataset(property_id: PropertyID) -> Dataset | None:
    """
    Fetch existing partial dataset for a property.

    This supports incremental updates where new documents are added
    to a property that already has partial data extracted.

    Args:
        property_id: Unique identifier for the property

    Returns:
        Existing dataset dict if found, None otherwise
    """
    _ensure_directories()

    dataset_path = DATASETS_DIR / f"{property_id}.json"

    if not dataset_path.exists():
        logger.debug(f"No existing dataset found for property {property_id}")
        return None

    try:
        with open(dataset_path, 'r') as f:
            dataset = json.load(f)

        logger.info(f" Loaded existing dataset for {property_id}")
        return dataset

    except Exception as e:
        logger.error(f"Failed to load existing dataset for {property_id}: {e}")
        return None


def get_linked_documents(property_id: PropertyID) -> list[DocumentTuple]:
    """
    Retrieve previously processed documents for a property.

    This enables the system to cross-reference new documents with
    old ones during incremental updates.

    Args:
        property_id: Unique identifier for the property

    Returns:
        List of (filename, pdf_bytes) tuples for previously processed docs
    """
    _ensure_directories()

    property_docs_dir = DOCUMENTS_DIR / property_id

    if not property_docs_dir.exists():
        logger.debug(f"No linked documents found for property {property_id}")
        return []

    documents = []

    try:
        for pdf_path in property_docs_dir.glob("*.pdf"):
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            documents.append((pdf_path.name, pdf_bytes))

        logger.info(f" Loaded {len(documents)} linked document(s) for {property_id}")
        return documents

    except Exception as e:
        logger.error(f"Failed to load linked documents for {property_id}: {e}")
        return []


def json_schema() -> dict:
    """
    Return the dataset JSON schema.

    This schema defines the expected structure and types for
    the extracted tax dataset.

    Returns:
        JSON schema dict
    """
    return DATASET_SCHEMA


def update_dataset(
    property_id: PropertyID,
    dataset: Dataset,
    documents: list[DocumentTuple] | None = None
) -> None:
    """
    Save the completed or updated dataset for a property.

    Also optionally saves the source documents for future reference
    (enables incremental updates with document linking).

    Args:
        property_id: Unique identifier for the property
        dataset: Complete dataset to save
        documents: Optional list of (filename, pdf_bytes) to archive
    """
    _ensure_directories()

    # Save dataset
    dataset_path = DATASETS_DIR / f"{property_id}.json"

    try:
        with open(dataset_path, 'w') as f:
            json.dump(dataset, f, indent=2)

        logger.info(f" Saved dataset for {property_id} to {dataset_path}")

    except Exception as e:
        logger.error(f"Failed to save dataset for {property_id}: {e}")
        raise

    # Optionally save documents for linking
    if documents:
        property_docs_dir = DOCUMENTS_DIR / property_id
        property_docs_dir.mkdir(parents=True, exist_ok=True)

        try:
            for filename, pdf_bytes in documents:
                # Use just the basename to avoid nested directories
                from pathlib import Path as PathLib
                doc_name = PathLib(filename).name
                doc_path = property_docs_dir / doc_name

                # Skip if already exists (don't overwrite)
                if doc_path.exists():
                    logger.debug(f"Document {doc_name} already archived, skipping")
                    continue

                with open(doc_path, 'wb') as f:
                    f.write(pdf_bytes)

            logger.info(f" Archived {len(documents)} document(s) for {property_id}")

        except Exception as e:
            logger.error(f"Failed to archive documents for {property_id}: {e}")
            # Non-fatal: dataset is saved, document archiving is optional


def get_all_property_ids() -> list[PropertyID]:
    """
    Get list of all property IDs that have datasets.

    Useful for batch processing and reporting.

    Returns:
        List of property IDs (without .json extension)
    """
    _ensure_directories()

    property_ids = [
        path.stem for path in DATASETS_DIR.glob("*.json")
    ]

    return sorted(property_ids)


def search_properties(
    address: str | None = None,
    parcel: str | None = None,
    county: str | None = None,
    tax_year: str | None = None,
    fuzzy: bool = False,
    fuzzy_threshold: float = 0.6,
) -> list[tuple[PropertyID, Dataset]]:
    """
    Search all processed properties by multiple criteria.

    All search parameters are case-insensitive and support partial matching.
    Multiple criteria are combined with AND logic.

    Args:
        address: Search by property address (partial match or fuzzy)
        parcel: Search by parcel number (partial match or fuzzy)
        county: Search by county name (partial match or fuzzy)
        tax_year: Search by tax year (exact match)
        fuzzy: Enable fuzzy matching for text fields (default: False)
        fuzzy_threshold: Minimum similarity ratio for fuzzy matches (0.0-1.0, default: 0.6)

    Returns:
        List of (property_id, dataset) tuples matching the criteria
    """
    from difflib import SequenceMatcher

    def fuzzy_match(query: str, target: str, threshold: float = 0.6) -> bool:
        """Check if query fuzzy matches target string."""
        if not target:
            return False

        # Case-insensitive comparison
        query_lower = query.lower()
        target_lower = target.lower()

        # First try exact substring match
        if query_lower in target_lower:
            return True

        # Then try fuzzy matching
        ratio = SequenceMatcher(None, query_lower, target_lower).ratio()
        return ratio >= threshold

    _ensure_directories()

    results: list[tuple[PropertyID, Dataset]] = []

    # Get all property IDs
    all_property_ids = get_all_property_ids()

    for property_id in all_property_ids:
        dataset = get_existing_dataset(property_id)

        if not dataset:
            continue

        # Apply filters
        matches = True

        # Address filter (case-insensitive partial match or fuzzy)
        if address:
            dataset_address = dataset.get("propertyAddress", "")
            if fuzzy:
                if not fuzzy_match(address, str(dataset_address), fuzzy_threshold):
                    matches = False
            else:
                if not dataset_address or address.lower() not in str(dataset_address).lower():
                    matches = False

        # Parcel filter (case-insensitive partial match or fuzzy)
        if parcel and matches:
            dataset_parcel = dataset.get("parcelNumber", "")
            if fuzzy:
                if not fuzzy_match(parcel, str(dataset_parcel), fuzzy_threshold):
                    matches = False
            else:
                if not dataset_parcel or parcel.lower() not in str(dataset_parcel).lower():
                    matches = False

        # County filter (case-insensitive partial match or fuzzy)
        if county and matches:
            dataset_county = dataset.get("county", "")
            if fuzzy:
                if not fuzzy_match(county, str(dataset_county), fuzzy_threshold):
                    matches = False
            else:
                if not dataset_county or county.lower() not in str(dataset_county).lower():
                    matches = False

        # Tax year filter (exact match)
        if tax_year and matches:
            dataset_year = dataset.get("taxYear", "")
            if str(dataset_year) != str(tax_year):
                matches = False

        if matches:
            results.append((property_id, dataset))

    logger.debug(f"Search found {len(results)} matching properties")
    return results


def delete_property_data(property_id: PropertyID) -> None:
    """
    Delete all data for a property (dataset + archived documents).

    Use with caution - this is permanent.

    Args:
        property_id: Unique identifier for the property
    """
    _ensure_directories()

    # Delete dataset
    dataset_path = DATASETS_DIR / f"{property_id}.json"
    if dataset_path.exists():
        dataset_path.unlink()
        logger.info(f"Deleted dataset for {property_id}")

    # Delete archived documents
    property_docs_dir = DOCUMENTS_DIR / property_id
    if property_docs_dir.exists():
        for doc_path in property_docs_dir.glob("*.pdf"):
            doc_path.unlink()
        property_docs_dir.rmdir()
        logger.info(f"Deleted archived documents for {property_id}")
