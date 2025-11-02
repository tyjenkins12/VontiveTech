"""Prompt templates for tax data extraction."""
import json

from src.state import Dataset


EXTRACTION_PROMPT = """SYSTEM PURPOSE
You are a vision+text extractor that reads property tax documents and outputs a single JSON object. Follow the deterministic rules exactly. Do your reasoning silently and return ONLY the final JSON.

ANCHORS
- CurrentDate (ISO): 2025-11-04
- Output MUST be valid JSON with the exact keys and types shown in SCHEMA.

SCHEMA (fixed keys)
{
  "taxYear": "YYYY",
  "annualizedAmountDue": 0.00,
  "amountDueAtClosing": 0.00,
  "county": "CountyName",
  "parcelNumber": "string",
  "nextTaxPaymentDate": "YYYY-MM-DD" | null,
  "followingTaxPaymentDate": "YYYY-MM-DD" | null,
  "propertyAddress": "string" | null,
  "_dateSelectionReasoning": "string explaining date selection logic"
}

**❗CRITICAL MULTI-DOCUMENT SCENARIO - OVERRIDES ALL OTHER PRIORITY RULES❗**
When you see BOTH of these conditions:
  A) Official county document showing a PAID historical tax year (e.g., "2024 PAID, $0 balance")
  AND
  B) Lender/servicer document showing UNPAID current/future year taxes (e.g., "June 2025 taxes UNPAID $1,118.23")

Then you MUST use this extraction logic (ignoring general document priority):
- **taxYear**: Extract the CURRENT year with UNPAID obligations → "2025" (NOT "2024")
- **annualizedAmountDue**: Use the official county document's total annual tax amount (for the year shown)
- **amountDueAtClosing**: Use the lender document's UNPAID amount → $1,118.23 (NOT $0.00)
- **nextTaxPaymentDate & followingTaxPaymentDate**: Use the lender document's payment schedule AS INPUT to the date selection algorithm. Apply the standard UNPAID date selection rules (30-day rollforward, etc.) to these dates.
- **Rationale**: For real estate closing purposes, buyers need to know CURRENT obligations, not fully paid historical years

**KEY INSIGHT - DIFFERENT TAX YEARS**:
- When documents discuss DIFFERENT TAX YEARS (e.g., official doc shows "2024 PAID" and lender shows "June 2025 UNPAID"), these are NOT conflicting information about the same tax year - they are separate tax years.
- DO NOT dismiss the lender document as "outdated" just because the official document has a more recent document date.
- The lender document is providing information about a MORE CURRENT TAX YEAR (2025) than the official document (2024).
- Extract the tax year and amounts that represent CURRENT UNPAID OBLIGATIONS (2025), not fully paid historical years (2024).
- Example: Official county doc dated 10/5/25 shows "2024 tax year PAID $0", Lender doc shows "June 2025 taxes $1,118.23 UNPAID" → Extract taxYear="2025", amountDueAtClosing=$1,118.23 (NOT taxYear="2024", amountDueAtClosing=$0.00)

DOCUMENT PRIORITY & MERGE (general - apply AFTER checking for CRITICAL SCENARIO above)
1) **RECENCY vs OFFICIALITY**: Official county/collector documents > lender/servicer > third-party summaries, EXCEPT when an unofficial document provides more recent information (more recent tax year, more current payment status, more recent document date). In those cases, the MORE RECENT information takes priority.
2) Newer documents override older; supplemental documents can fill missing fields.
3) If sources disagree, prefer the most official AND most recent. When you must choose between officiality and recency, choose RECENCY. See DATE-SOURCE OVERRIDE for the date fields.

DATE-SOURCE OVERRIDE (applies ONLY to next/following dates)
- Default: prefer dates from more official documents.






- Override: if a less-official document has a CLEARLY MORE RECENT document date/revision/issue timestamp than the official one, USE THE LESS-OFFICIAL DOCUMENT'S DATES.

FIELD RULES (deterministic)

A) taxYear (string)
- Use the year explicitly labeled as the current bill/certificate fiscal year (e.g., "2025-2026" → "2025").
- Look for explicit labels like "Tax Year", "Assessment Year", "Fiscal Year" on the bill or certificate.
- **CRITICAL**: Extract the TAX YEAR that this certificate/document pertains to, NOT the year of future payment due dates.
- Priority order for determining taxYear:
  1. Explicit "Tax Year" or "Assessment Year" label
  2. Year that taxes were PAID (e.g., "Taxes paid: 9/1/2025" → taxYear = "2025")
  3. Certificate/document issue date year
  4. Current payment schedule year (NOT future due dates)
- Example: Document dated 2025 shows "Taxes paid 9/1/2025" and "Due 8/31/2026" → taxYear = "2025" (NOT "2026")

B) annualizedAmountDue (number)
- Sum ALL current-year taxes/assessments (county/city/school/special districts).
- EXCLUDE prior-year delinquencies, penalties, interest.
- If installments appear, sum all installments for the full-year total.
- **CRITICAL**: If both official county document and unofficial calculation worksheets are present, use the official county document's ACTUAL BILL AMOUNT (net amount after exemptions/adjustments), NOT the gross amount from worksheets.
- Example: Official bill shows $7,093.80, worksheet shows $7,169.59 (gross before exemptions) → Use $7,093.80

C) amountDueAtClosing (number)
- Sum ALL unpaid amounts that are overdue or currently due as of CurrentDate (2025-11-04).
- **CRITICAL for semi-annual taxes**: If MULTIPLE installments have due dates before CurrentDate, sum ALL of them.
  * Example: April 30 payment ($874.51) + October 31 payment ($874.52) both past due → sum BOTH = $1,749.03
  * DO NOT report just the most recent overdue installment - report the TOTAL overdue amount
- If the current-year bill is fully PAID with $0 balance, set to 0.00.
- Ignore column headers labeled "Due" that are not statuses.

D) county (string)
- Extract county/parish name and REMOVE the word "County"/"Parish".

E) parcelNumber (string)
- The APN/Parcel. Prefer fields explicitly named "Parcel Number", "Parcel ID", "APN".
- **CRITICAL**: If both "Parcel Number" and "Tax Account Number" are present, use the Parcel Number (NOT the Tax Account).
- May include dashes/letters. Do not substitute a situs address.

F) propertyAddress (string | null)
- Extract the full physical address if present.
- Look for "Property Address", "Site Address", "Situs Address", "Location".
- Return null if not found.

G) Payment Dates — nextTaxPaymentDate & followingTaxPaymentDate
CRITICAL: **ALWAYS extract payment dates even if taxes are fully PAID**. Payment schedules exist independently of payment status.

GOAL
- nextTaxPaymentDate: the installment date **closest to CurrentDate** (regardless of past or future).
- followingTaxPaymentDate: the next scheduled installment **strictly after** nextTaxPaymentDate (roll into next year if needed).
- For these two fields, apply DATE-SOURCE OVERRIDE when choosing between conflicting source documents.

ALGORITHM
1) COLLECT candidates:
   - Extract ALL installment/due/face/payment dates from coupons, schedules, headers/footers.
   - For each candidate, capture: {payment_date_raw, source_type (official/unofficial), document_timestamp (issue/revision/statement date if visible), page/provenance}.
   - **DO NOT skip dates just because taxes are PAID** - extract the payment schedule regardless.
2) NORMALIZE to YYYY-MM-DD:
   - If only month/day is shown, infer the year from the taxYear and the schedule order on the document.
   - Respect explicit cadence labels (e.g., "1st/2nd Installment"). Keep that order; roll years as needed.
3) ELIGIBILITY:
   - ALL normalized dates are eligible candidates.
   - DO NOT filter out past dates - they may be the closest to CurrentDate.
4) RANK & SELECT nextTaxPaymentDate:
   - Compute abs_days = |payment_date - CurrentDate| for ALL candidates.
   - **IF amountDueAtClosing = 0.00 (taxes are PAID)**:
     * Filter candidates to ONLY future dates (payment_date >= CurrentDate 2025-11-04)
     * If ANY future dates exist: Select the EARLIEST future date and STOP. Do NOT roll forward.
     * If NO future dates exist: Roll ALL candidate dates forward +1 year, then select the earliest
     * CRITICAL: Any date >= CurrentDate in the payment schedule represents an upcoming payment. Use it as-is.
     * Example: Candidates [2025-02-10, 2025-04-30, 2025-12-31], CurrentDate=2025-11-04, PAID
       → Future dates exist: [2025-12-31] → Select 2025-12-31 (the upcoming December payment)
     * Example: Candidates [2025-02-10, 2025-04-30, 2025-10-31], CurrentDate=2025-11-04, PAID
       → No future dates → Roll all forward: [2026-02-10, 2026-04-30, 2026-10-31] → Select 2026-02-10
   - **IF amountDueAtClosing > 0 (taxes are UNPAID)**:
     * Step 1: Check for future dates (>= CurrentDate). If any exist, select the EARLIEST future date. DONE.
     * Step 2: All dates are past. Find the closest past date to CurrentDate.
     * Step 3: Is closest past date within 30 days? If YES → Use it. DONE. If NO → Roll forward one cycle.
     * CRITICAL: Once you select a date per these steps, STOP. Do NOT say "However", "but", "CORRECTION", or reconsider.
     * DO NOT override based on "both installments overdue", "earliest overdue payment", "current unpaid obligation", or "immediate next payment" logic.
     * The 30-day rule determines selection. Follow it exactly, even if the document explicitly mentions an unpaid amount for that past-due date.
     * Example: Document shows "July 2025 taxes $1,118 UNPAID" but July 31 is 96 days past (>30) → Roll to next cycle (2026-02-28), NOT 2025-07-31.
     * Example: Candidates [2025-04-30 (188 past), 2025-10-31 (4 past)], CurrentDate=2025-11-04, UNPAID
       → Step 1: No future dates. Step 2: Closest = 2025-10-31 (4 past). Step 3: Within 30 days? YES → Use 2025-10-31
     * Example: Candidates [2025-02-28 (249 past), 2025-07-31 (96 past)], CurrentDate=2025-11-04, UNPAID
       → Step 1: No future. Step 2: Closest = 2025-07-31 (96 past). Step 3: Within 30 days? NO → Roll to 2026-02-28
   - Tie-breaker (same distance/date): prefer OFFICIAL … UNLESS an UNOFFICIAL candidate's document_timestamp is clearly more recent → choose the UNOFFICIAL candidate (DATE-SOURCE OVERRIDE).
5) SELECT followingTaxPaymentDate:
   - Choose the next scheduled installment strictly later than nextTaxPaymentDate according to the visible cadence on the SAME SOURCE first.
   - If the cadence on that source is incomplete, search other sources; maintain schedule order; roll into next calendar year if needed.
   - **INFERENCE RULE**: If a clear payment schedule/cadence is evident, infer the following date even if not explicitly shown:
     * Annual: If taxes are due once per year (e.g., March 31), infer next year's date (e.g., 2026-03-31 → 2027-03-31)
     * Semi-annual: If taxes are due twice per year (e.g., Apr 30 & Oct 31), infer the next installment
     * Quarterly: If taxes are due four times per year, infer the next quarter
6) VALIDATE:
   - followingTaxPaymentDate must be > nextTaxPaymentDate; if not, roll forward one cycle/year and re-validate.
   - If a valid following date cannot be derived, set it to null.

H) _dateSelectionReasoning (string)
- Explain your date selection logic step-by-step:
  1. List all payment date candidates found in the documents (with raw values)
  2. Show normalized dates in YYYY-MM-DD format
  3. Show the distance calculation (abs_days from CurrentDate) for ALL candidates
  4. Explain which date was selected as nextTaxPaymentDate and why (smallest distance, tie-breakers applied)
  5. Explain which date was selected as followingTaxPaymentDate and why (next in schedule, year rolled if needed)
  6. If taxes are PAID, confirm that dates were still extracted per the CRITICAL rule
- This field is for debugging purposes and helps validate the date selection algorithm

OUTPUT
- Return ONLY the JSON with SCHEMA keys in the order shown.
- Use null for missing/unreliable values.
- IMPORTANT: Include the _dateSelectionReasoning field with detailed explanation of date selection.
"""


def create_extraction_prompt_with_existing(
    existing_dataset: Dataset | None,
    doc_count: int
) -> str:
    """
    Create an extraction prompt that handles existing partial data.

    Args:
        existing_dataset: Previously extracted partial data (if any)
        doc_count: Number of new documents being processed

    Returns:
        Formatted prompt string
    """
    if not existing_dataset:
        return EXTRACTION_PROMPT

    existing_json = json.dumps(existing_dataset, indent=2)

    return f"""You are analyzing property tax documents WITH existing partial data.

EXISTING DATA (may be incomplete):
{existing_json}

NEW DOCUMENTS:
{doc_count} new document(s) provided for analysis.

YOUR TASK:
1. Extract the 7 required fields from the new documents
2. Compare with existing data
3. Determine if new documents:
   - SUPPLEMENT existing data (add missing fields, provide updated values)
   - SUPERSEDE existing data (newer versions, revised certificates)
4. Return the COMPLETE, MERGED dataset

MERGING RULES:
1. **Source Priority** (MOST IMPORTANT):
   - Official county/government documents ALWAYS override unofficial documents
   - If existing data came from unofficial source and new document is official: Use new official values
   - If existing data came from official source and new document is unofficial: Keep existing official values
   - When both are official or both unofficial: Apply other rules below

2. **Recency**:
   - If new document has newer date/revision: Use new values
   - If new document is SUPPLEMENTAL (additional tax types): Add to existing amounts where appropriate

3. **Completeness**:
   - If field is missing in both: Use null
   - Always prefer most recent, most complete information from the highest priority source
   - For dates: use the most recent payment schedule from official sources

**CRITICAL**: You MUST return ONLY valid JSON. Do NOT include any explanations, commentary, or conversational text.
Return the JSON object immediately without any preamble.

{EXTRACTION_PROMPT.split('SCHEMA (fixed keys)')[1]}

**REMINDER**: Your response must be ONLY the JSON object shown in the OUTPUT FORMAT above.
Do NOT start with phrases like "Looking at these documents" or "I can see".
Return pure JSON only."""
