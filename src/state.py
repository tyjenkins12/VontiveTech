"""State definitions for the tax certificate extraction agent."""
from typing import TypedDict, Unpack

# Python 3.12+ type aliases for semantic clarity
type PropertyID = str
type FilePath = str
type DocumentTuple = tuple[str, bytes]
type Dataset = dict[str, str | float | None]
type ValidationIssue = dict[str, str]
type ExtractionMethod = str  # "text" or "vision"


class AgentState(TypedDict):
    """State for the tax certificate extraction agent.

    Supports incremental updates with existing datasets and linked documents.
    """

    # Input
    property_id: PropertyID
    zip_file_path: FilePath
    existing_dataset: Dataset | None  # Previously extracted data
    linked_documents: list[DocumentTuple]  # Previously processed PDFs

    # Processing
    new_documents: list[DocumentTuple]  # Fresh PDFs to process
    all_documents: list[DocumentTuple]  # Combined documents
    extracted_data: Dataset | None

    # Output
    final_dataset: Dataset
    validation_issues: list[ValidationIssue]

    # Metadata
    processing_log: list[str]
    extraction_method: ExtractionMethod | None  # "text" or "vision"


def create_agent_state(
    property_id: PropertyID,
    zip_file_path: FilePath,
    **kwargs: Unpack[AgentState]
) -> AgentState:
    """
    Create an AgentState with type-safe defaults.

    Python 3.12+ PEP 692 enables IDE autocomplete for AgentState fields.

    Args:
        property_id: Unique property identifier
        zip_file_path: Path to the zip file containing tax documents
        **kwargs: Additional AgentState fields to override defaults

    Returns:
        Complete AgentState with all required fields
    """
    defaults: AgentState = {
        "property_id": property_id,
        "zip_file_path": zip_file_path,
        "existing_dataset": None,
        "linked_documents": [],
        "new_documents": [],
        "all_documents": [],
        "extracted_data": None,
        "final_dataset": {},
        "validation_issues": [],
        "processing_log": [],
        "extraction_method": None,
    }
    return {**defaults, **kwargs}
