# Tax Certificate Dataset Agent - Technical Interview Challenge

## Overview

Welcome to the Vontive dataset agent challenge! This take-home assignment will evaluate your ability to build complex AI agents to perform tasks with messy production data.

In real-world underwriting workflows, loan processors need to analyze multiple tax documents for a single property to extract critical information like tax amounts, payment dates, parcel numbers, and county information. Your task is to build a simplified version of this system.

The zip files under the tax_certificates directory are grouped together by property, each zip represents one property, and the documents are all related to each other.

## The Challenge

Build an AI agent that:
1. **Processes multiple tax certificate documents** for a single property dataset
2. **Extracts structured data** from these documents into a predefined schema
3. **Handles incremental updates** - the agent should work with existing partial data and new documents
4. **Produces a complete, validated dataset** conforming to the required JSON schema

## Dataset Schema

Your agent must extract the following fields and return them as a JSON object (values here are just for example):

```json
{
  "taxYear": "2024",                      // 4-digit year (string, pattern: "^(20[0-9]{2})$")
  "annualizedAmountDue": 1378.24,         // Total annual tax amount (number), summed across multiple jurisdictions, should not include delinquent taxes
  "amountDueAtClosing": 1816.79,          // Amount due at loan closing (number), includes delinquent and unpaid overdue taxes
  "county": "Allegheny",                  // County name without "County" suffix (string)
  "parcelNumber": "0879-J-00220-0000-00", // Property parcel/APN/tax ID (string)
  "nextTaxPaymentDate": "2024-08-31",     // Next payment date (ISO date string)
  "followingTaxPaymentDate": "2025-04-30" // Following payment date (ISO date string)
}
```

### Field Requirements

- **taxYear**: The year the tax certificate covers
- **annualizedAmountDue**: Sum of ALL taxes for the year (county, school, fire, water, sewer, etc.), regardless of payment status. Do NOT include delinquent amounts from previous years.
- **amountDueAtClosing**: Outstanding balance still owed by the loan closing date
- **county**: Must be a valid U.S. county name (without "County" or "Parish" suffix)
- **parcelNumber**: Unique property identifier (NOT the property address)
- **nextTaxPaymentDate**: Must be after today's date
- **followingTaxPaymentDate**: Must be after the next tax payment date

## Example Scenario

You'll receive:
- **Existing dataset**: Partial data from previous document processing (may be empty or incomplete)
- **Documents**: Fresh documents to process that may be:
  - Supplemental information (additional tax types, updated amounts)
  - Newer versions that supersede existing documents

Your agent must:
1. Retrieve existing dataset data. 
2. Determine relationships between new and existing documents
3. Extract data from all relevant documents
4. Merge information intelligently (newer documents override older ones)
5. Return a complete, validated dataset

## Technical Requirements

### Suggested Technology
- **LangGraph (or similar)** for agent orchestration
- **Claude (Anthropic)** as the model (claude-sonnet-4-20250514 or similar)
- **Python 3.12+**
- **uv** for package management

You are free to use any model you wish. If you do not have your own API key for model access, we can provide you with an Anthropic API key.


### Suggested Agent Structure

You may use either:
1. **Single-agent approach**: One agent handles all extraction
2. **Multi-agent approach**: Break down by subtasks

### Suggested Tools

Some Suggestions on tools you may want to give your agent:
- `get_existing_dataset()`: Fetches existing partial data
- `get_linked_documents()`: Retrieves previously processed documents
- `json_schema()`: Returns the dataset schema
- `update_dataset(completed_dataset: dict)`: Saves the completed dataset

## Evaluation Criteria

Your submission will be evaluated on:

### 1. Code Quality (30%)
- Clean, readable, well-structured code
- Proper type hints and documentation
- Follows Python best practices
- Clear separation of concerns

### 2. Agent Design (30%)
- Appropriate use of Context Engineering patterns
- Effective agent/tool decomposition
- Proper state management

### 3. Accuracy (25%)
- Correctly extracts all required fields
- Handles edge cases (missing data, conflicting documents)
- Properly merges old and new information
- Validates output against schema

### 4. Documentation (15%)
- Clear README with setup instructions
- Code comments where helpful
- Example inputs/outputs
- Architecture explanation

## Deliverables

Submit a repository containing:

1. **Source code** (`src/` directory)
   - Agent implementation
   - State definitions
   - Tool implementations
   - config if needed

2. **README.md** with:
   - Setup instructions
   - How to run your agent
   - Architecture overview
   - Design decisions and tradeoffs

3. **Requirements file** (`pyproject.toml` or equivalent)

4. **Example test case** demonstrating your agent working with sample data

5. **(Bonus)** Unit tests for key components


## Time Expectation

This challenge should take approximately **2-4 hours** to complete. We value quality over speed—focus on building a well-architected, working solution rather than rushing through it.

If you do not have a fully working solution after the allotted time period, that's totally fine! But be prepared to explain your design choices, and the future changes you would make to complete it.

## Questions?

If you have questions about requirements or need clarification, please reach out to Zach (z.loubier@vontive.com) or Sahil (s.agarwal@vontve.com). We are happy to help!

## Bonus Points

- Implement proper error handling and logging
- Add validation logic to ensure reasonable outputs
- Handle edge cases (e.g., missing documents, incomplete information)
- Write unit tests for tools and state transitions
- Use thinking tokens for complex reasoning
- Implement a simple CLI or demo script to showcase your agent

---

Good luck! We're excited to see your approach to building an intelligent document processing agent.
