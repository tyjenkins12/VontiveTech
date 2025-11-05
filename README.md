# Tax Certificate Dataset Agent

AI agent for extracting structured tax data from property tax certificates using LangGraph orchestration and Claude Sonnet 4.5 with hybrid text/vision extraction.

## Features

- **Multi-document processing** - Handles multiple tax certificates per property with intelligent merging
- **Incremental updates** - Merges new documents with existing data using document priority rules
- **Hybrid extraction** - Routes to text-only API when possible for 60-70% cost savings
- **Schema validation** - Validates 7 required fields with business rule checks
- **Property search** - Query by address, parcel, county, or year with fuzzy matching
- **94%+ accuracy** - Advanced prompt engineering handles complex multi-document scenarios

## Setup

### Prerequisites
- Python 3.12+
- Anthropic API key

### Installation

```bash
# Clone and setup
git clone https://github.com/tyjenkins12/VontiveTech.git
cd VontiveTech

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Configure API key
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Basic Commands

```bash
# Interactive extraction
python -m src.main extract

# Extract specific property
python -m src.main extract -n "1760629159052"

# Batch process all properties
python -m src.main batch --input-dir tax_certificates

# Search properties
python -m src.main search --county "Spokane" --interactive

# List processed properties
python -m src.main list-properties
```

### Output

Extracted datasets saved to:
- JSON: `output/datasets/{property_id}.json`
- PDFs: `output/documents/{property_id}/`

## Architecture

### LangGraph 6-Node Workflow

1. **load_existing** - Fetch existing dataset + documents for incremental updates
2. **load_documents** - Extract PDFs from zip
3. **extract** - Hybrid text/vision extraction with quality assessment
4. **merge** - Merge new data with existing dataset
5. **validate** - Schema + business rule validation
6. **save** - Persist dataset and archive documents

![img.png](img.png)

### Key Components

```
src/
├── agent/graph.py          # LangGraph orchestration
├── extraction/
│   ├── extractor.py        # Hybrid text/vision extraction
│   └── prompts.py          # Advanced prompts with multi-doc logic
├── validation/validator.py # Schema + business rules
├── tools/
│   ├── document_loader.py  # PDF loading + quality assessment
│   ├── dataset_tools.py    # Persistence + search
│   └── test_accuracy.py    # Ground truth comparison
└── main.py                 # CLI interface
```

## Key Design Decisions

### 1. Hybrid Text/Vision Extraction

Quality-based routing saves 60-70% on API costs:
- Text extraction: 500+ chars, 3+ tax keywords, <10 gibberish words
- Falls back to vision when text quality is poor

### 2. Incremental Updates

Two-layer merging strategy:
- **Layer 1**: Claude sees existing data in prompt for intelligent merging
- **Layer 2**: Code-level fallback fills missing fields

### 3. Advanced Prompt Engineering

Handles complex scenarios like:
- Official doc shows "2024 PAID" + Lender shows "2025 UNPAID $1,118"
- Recency vs officiality: Recent information takes priority
- 30-day rollforward rule for UNPAID taxes

Result: 94%+ accuracy on multi-document scenarios

### 4. Property Search

- Partial matching on address, parcel, county
- Fuzzy matching for typos
- Multiple output formats (JSON, table, CSV)
- Interactive selection with export

## Testing

```bash
# Single property test
python -m src.main extract -n "1760629159052"

# Batch test
python -m src.main batch

# Accuracy test
python tests/consolidate_results.py
python src/tools/test_accuracy.py
```

## Performance

| Metric              | Value              |
|---------------------|-------------------|
| Success Rate        | 100% (10/10)      |
| Overall Accuracy    | 94.29%            |
| Perfect Extractions | 7/10 properties   |
| Text Extraction     | 20% of properties |
| Cost Savings        | ~20% vs vision-only |

**Field accuracy:**
- Core fields (taxYear, amounts, county): 100%
- Parcel numbers: 90%
- Payment dates: 90%
