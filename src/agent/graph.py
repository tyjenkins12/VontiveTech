"""LangGraph orchestration for tax certificate extraction."""
from langgraph.graph import StateGraph, END
from loguru import logger

from src.state import AgentState, PropertyID, FilePath, create_agent_state
from src.tools.document_loader import load_property_documents
from src.tools.dataset_tools import (
    get_existing_dataset,
    get_linked_documents,
    update_dataset
)
from src.extraction.extractor import TaxDataExtractor
from src.validation.validator import DatasetValidator


# Initialize components
extractor = TaxDataExtractor()
validator = DatasetValidator()


# === NODE FUNCTIONS ===

def load_existing_node(state: AgentState) -> AgentState:
    """
    Load existing dataset and linked documents for incremental updates.

    This node checks if the property already has partial data extracted
    from previous processing runs.
    """
    logger.info(f"📂 Loading existing data for property: {state['property_id']}")

    existing_dataset = get_existing_dataset(state['property_id'])
    linked_documents = get_linked_documents(state['property_id'])

    state['existing_dataset'] = existing_dataset
    state['linked_documents'] = linked_documents

    if existing_dataset:
        logger.info(f"✅ Found existing dataset with {len(existing_dataset)} fields")
        state['processing_log'].append(f"Loaded existing dataset ({len(existing_dataset)} fields)")
    else:
        logger.info("No existing dataset found (new property)")
        state['processing_log'].append("No existing dataset (new property)")

    if linked_documents:
        logger.info(f"✅ Found {len(linked_documents)} linked document(s)")
        state['processing_log'].append(f"Loaded {len(linked_documents)} linked documents")

    return state


def load_documents_node(state: AgentState) -> AgentState:
    """
    Extract PDF documents from the property zip file.

    This loads the new documents that need to be processed.
    """
    logger.info(f"📄 Loading documents from: {state['zip_file_path']}")

    new_documents = load_property_documents(state['zip_file_path'])

    state['new_documents'] = new_documents
    state['all_documents'] = state['linked_documents'] + new_documents

    logger.info(f"✅ Loaded {len(new_documents)} new document(s)")
    logger.info(f"Total documents available: {len(state['all_documents'])}")

    state['processing_log'].append(f"Loaded {len(new_documents)} new documents")

    return state


def extract_node(state: AgentState) -> AgentState:
    """
    Extract tax data using hybrid text/vision approach.

    This node intelligently routes to text-only or vision extraction
    based on PDF text quality.
    """
    logger.info("🔍 Extracting tax data from documents")

    # Use new documents for extraction (existing data passed for merging context)
    extracted_data = extractor.extract(
        documents=state['new_documents'],
        existing_dataset=state['existing_dataset']
    )

    state['extracted_data'] = extracted_data

    # Log extraction method used
    stats = extractor.get_extraction_stats()
    if stats['total_extractions'] > 0:
        method = "text" if state['new_documents'] and stats['text_extractions'] > stats['vision_extractions'] else "vision"
        state['extraction_method'] = method
        logger.info(f"Used {method} extraction")
        state['processing_log'].append(f"Extraction method: {method}")

    logger.info("✅ Data extraction complete")

    return state


def merge_node(state: AgentState) -> AgentState:
    """
    Merge extracted data with existing dataset.

    This handles the intelligent merging logic when incremental updates occur.
    Note: The extractor already does most merging, but we can add additional
    logic here if needed.
    """
    logger.info("🔄 Merging data")

    # If we have both existing and new data, ensure completeness
    if state['existing_dataset'] and state['extracted_data']:
        merged = state['extracted_data'].copy()

        # Fill in any missing fields from existing data
        # (Claude may have returned updated/merged data already)
        for key, value in state['existing_dataset'].items():
            if key not in merged or merged[key] is None:
                merged[key] = value
                logger.debug(f"Retained existing value for {key}")

        state['final_dataset'] = merged
        logger.info("✅ Merged existing and new data")
        state['processing_log'].append("Merged with existing dataset")

    elif state['extracted_data']:
        state['final_dataset'] = state['extracted_data']
        logger.info("✅ Using extracted data (no existing dataset)")
        state['processing_log'].append("Using new extraction (no merge needed)")

    else:
        # Shouldn't happen, but handle gracefully
        state['final_dataset'] = state['existing_dataset'] or {}
        logger.warning("No extracted data available")
        state['processing_log'].append("Warning: No extracted data")

    return state


def validate_node(state: AgentState) -> AgentState:
    """
    Validate the final dataset against schema and business rules.

    This ensures data quality before saving.
    """
    logger.info("✅ Validating final dataset")

    is_valid, errors = validator.validate(state['final_dataset'])

    # Store validation results
    state['validation_issues'] = [
        {"type": "error", "message": error} for error in errors
    ]

    if is_valid:
        logger.info("✅ Validation passed")
        state['processing_log'].append("Validation: PASSED")
    else:
        logger.warning(f"⚠️ Validation found {len(errors)} issue(s)")
        state['processing_log'].append(f"Validation: {len(errors)} issues found")

    return state


def save_node(state: AgentState) -> AgentState:
    """
    Save the final dataset and archive documents.

    This persists the results for future incremental updates.
    """
    logger.info(f"💾 Saving dataset for property: {state['property_id']}")

    update_dataset(
        property_id=state['property_id'],
        dataset=state['final_dataset'],
        documents=state['new_documents']
    )

    logger.info("✅ Dataset saved successfully")
    state['processing_log'].append("Dataset saved")

    return state


# === GRAPH CONSTRUCTION ===

def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph agent workflow.

    Flow:
    1. Load existing data (if any)
    2. Load new documents from zip
    3. Extract data using hybrid approach
    4. Merge with existing data
    5. Validate final dataset
    6. Save results

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("load_existing", load_existing_node)
    workflow.add_node("load_documents", load_documents_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("merge", merge_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("save", save_node)

    # Define edges (linear workflow)
    workflow.set_entry_point("load_existing")
    workflow.add_edge("load_existing", "load_documents")
    workflow.add_edge("load_documents", "extract")
    workflow.add_edge("extract", "merge")
    workflow.add_edge("merge", "validate")
    workflow.add_edge("validate", "save")
    workflow.add_edge("save", END)

    # Compile graph
    return workflow.compile()


def run_extraction_agent(
    property_id: PropertyID,
    zip_file_path: FilePath
) -> AgentState:
    """
    Run the complete extraction workflow for a property.

    Python 3.12+ uses semantic type aliases for better code clarity.

    Args:
        property_id: Unique identifier for the property
        zip_file_path: Path to zip file containing tax PDFs

    Returns:
        Final AgentState with extracted dataset and metadata
    """
    logger.info(f"🚀 Starting extraction agent for property: {property_id}")

    # Initialize state using type-safe helper (Python 3.12+ PEP 692)
    initial_state = create_agent_state(
        property_id=property_id,
        zip_file_path=zip_file_path
    )

    # Create and run graph
    graph = create_agent_graph()
    final_state = graph.invoke(initial_state)

    logger.info(f"✅ Extraction complete for property: {property_id}")

    return final_state
