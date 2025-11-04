"""Hybrid text/vision extraction for tax documents."""
from anthropic import Anthropic
import json
import base64
from loguru import logger

from src.config import MODEL, MAX_TOKENS, TEMPERATURE, ANTHROPIC_API_KEY
from src.extraction.prompts import EXTRACTION_PROMPT, create_extraction_prompt_with_existing
from src.tools.document_loader import extract_text_from_pdf, assess_text_quality
from src.state import DocumentTuple, Dataset


class TaxDataExtractor:
    """Extract tax data using hybrid text/vision approach for cost optimization."""

    def __init__(self):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.text_extraction_count = 0
        self.vision_extraction_count = 0

    def extract(
        self,
        documents: list[DocumentTuple],
        existing_dataset: Dataset | None = None
    ) -> Dataset:
        """
        Extract data from property tax documents using hybrid approach.

        Strategy:
        1. Try text extraction for each document
        2. If all documents have good text → use text-only Claude (cheaper)
        3. If any document has poor text → use vision Claude (robust)

        Args:
            documents: List of (filename, pdf_bytes) tuples
            existing_dataset: Optional partial dataset from previous processing

        Returns:
            Extracted dataset as dict
        """
        logger.info(f"Extracting data from {len(documents)} document(s)")

        # Attempt text extraction from all documents
        extracted_texts = []
        all_text_good = True

        for filename, pdf_bytes in documents:
            text = extract_text_from_pdf(pdf_bytes)

            if text and assess_text_quality(text):
                extracted_texts.append(f"=== {filename} ===\n{text}")
                logger.info(f" {filename}: Good text extraction")
            else:
                all_text_good = False
                logger.info(f" {filename}: Poor/no text, will use vision")
                break  # Stop checking, we'll use vision

        # Route to appropriate extraction method
        if all_text_good and extracted_texts:
            result = self._extract_from_text(extracted_texts, existing_dataset)
            self.text_extraction_count += 1
            logger.info(" Used text-only extraction (cost-efficient)")
        else:
            result = self._extract_from_vision(documents, existing_dataset)
            self.vision_extraction_count += 1
            logger.info(" Used vision extraction (robust)")

        return result

    def _extract_from_text(
        self,
        texts: list[str],
        existing_dataset: Dataset | None = None
    ) -> Dataset:
        """
        Extract using text-only Claude (cheaper).

        Args:
            texts: List of extracted text strings
            existing_dataset: Optional partial dataset from previous processing

        Returns:
            Extracted dataset as dict
        """
        combined_text = "\n\n".join(texts)

        # Use appropriate prompt based on whether we have existing data
        system_prompt = create_extraction_prompt_with_existing(
            existing_dataset,
            len(texts)
        )

        # Use standard text API (much cheaper than vision)
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": f"Here are the tax documents in text format:\n\n{combined_text}\n\nPlease extract the dataset."
                }]
            )

            result = self._parse_response(response.content[0].text)
            logger.info(" Text-only extraction successful")

            # Log token usage
            logger.info(
                f"Token usage - Input: {response.usage.input_tokens}, "
                f"Output: {response.usage.output_tokens}"
            )

            return result

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            raise

    def _extract_from_vision(
        self,
        documents: list[DocumentTuple],
        existing_dataset: Dataset | None = None
    ) -> Dataset:
        """
        Extract using Claude vision (more expensive, more robust).

        Args:
            documents: List of (filename, pdf_bytes) tuples
            existing_dataset: Optional partial dataset from previous processing

        Returns:
            Extracted dataset as dict
        """
        # Use appropriate prompt based on whether we have existing data
        system_prompt = create_extraction_prompt_with_existing(
            existing_dataset,
            len(documents)
        )

        # Build message content with PDFs
        content = []

        for filename, pdf_bytes in documents:
            # Validate PDF before sending
            try:
                from pypdf import PdfReader
                import io
                # Quick validation - try to read the PDF
                PdfReader(io.BytesIO(pdf_bytes))
            except Exception as e:
                logger.warning(f"Skipping invalid/corrupted PDF {filename}: {e}")
                logger.warning(f"This may result in incomplete extraction")
                continue

            # Claude can read PDFs directly
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode('utf-8')
                }
            })

        # Add instruction
        content.append({
            "type": "text",
            "text": "Please extract the tax dataset from these documents."
        })

        # Call Claude with vision
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": content}]
            )

            if not response.content:
                logger.error("API returned empty content!")
                raise ValueError("API response has no content")

            result = self._parse_response(response.content[0].text)
            logger.info(" Vision extraction successful")

            # Log token usage
            logger.info(
                f"Token usage - Input: {response.usage.input_tokens}, "
                f"Output: {response.usage.output_tokens}"
            )

            return result

        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            raise

    def _parse_response(self, text: str) -> Dataset:
        """
        Parse JSON from Claude response.

        Args:
            text: Response text from Claude

        Returns:
            Parsed JSON as dict

        Raises:
            ValueError: If response is not valid JSON
        """
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Raw response: {text[:500]}")
            raise ValueError("Claude did not return valid JSON")

    def get_extraction_stats(self) -> dict[str, int | float]:
        """
        Return statistics on extraction method usage.

        Returns:
            Dict with extraction statistics
        """
        total = self.text_extraction_count + self.vision_extraction_count
        if total == 0:
            return {
                "text_extractions": 0,
                "vision_extractions": 0,
                "text_percentage": 0.0
            }

        return {
            "text_extractions": self.text_extraction_count,
            "vision_extractions": self.vision_extraction_count,
            "text_percentage": (self.text_extraction_count / total) * 100,
            "total_extractions": total
        }
