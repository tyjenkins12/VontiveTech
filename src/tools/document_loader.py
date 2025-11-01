"""Document loading and text extraction utilities."""
import zipfile
from pathlib import Path
import io
from pypdf import PdfReader
from loguru import logger

from src.state import FilePath, DocumentTuple


def load_property_documents(zip_path: FilePath) -> list[DocumentTuple]:
    """
    Extract PDF files from a property zip.

    Args:
        zip_path: Path to the zip file

    Returns:
        List of (filename, pdf_bytes) tuples
    """
    documents = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.filelist:
                # Skip macOS metadata files (__MACOSX folder and ._ files)
                if '__MACOSX' in file_info.filename:
                    continue
                if Path(file_info.filename).name.startswith('._'):
                    continue

                if file_info.filename.lower().endswith('.pdf'):
                    pdf_bytes = zip_ref.read(file_info.filename)
                    documents.append((file_info.filename, pdf_bytes))
                    logger.info(f"Loaded: {file_info.filename} ({len(pdf_bytes)} bytes)")

        logger.info(f"✅ Loaded {len(documents)} PDF(s) from {Path(zip_path).name}")
        return documents

    except Exception as e:
        logger.error(f"Failed to load documents from {zip_path}: {e}")
        raise


def extract_text_from_pdf(pdf_bytes: bytes) -> str | None:
    """
    Extract embedded text from PDF.

    Args:
        pdf_bytes: PDF file content as bytes

    Returns:
        Extracted text if successful, None if extraction fails
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []

        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)

        if full_text.strip():
            logger.debug(f"Extracted {len(full_text)} characters from PDF ({len(reader.pages)} pages)")
            return full_text
        else:
            logger.debug("PDF has no extractable text")
            return None

    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        return None


def assess_text_quality(text: str) -> bool:
    """
    Determine if extracted text is good enough for text-only processing.

    Heuristics:
    - Minimum length (500 chars for tax docs)
    - Contains expected tax-related keywords
    - Not garbled (reasonable word-to-gibberish ratio)

    Args:
        text: Extracted text to assess

    Returns:
        True if text quality is sufficient, False otherwise
    """
    if not text or len(text) < 500:
        logger.debug("Text too short for reliable extraction")
        return False

    # Check for tax-related keywords
    keywords = [
        'tax', 'parcel', 'county', 'amount', 'due', 'payment',
        'property', 'assessed', 'levy', 'bill'
    ]
    text_lower = text.lower()
    keyword_matches = sum(1 for kw in keywords if kw in text_lower)

    if keyword_matches < 3:
        logger.debug(f"Only {keyword_matches} tax keywords found (need 3+)")
        return False

    # Check for reasonable word density
    words = text.split()
    if len(words) < 100:
        logger.debug("Too few words for tax document")
        return False

    # Check for excessive gibberish (words with many consecutive consonants)
    sample_words = words[:50]  # Check first 50 words
    gibberish_count = 0

    for word in sample_words:
        if len(word) > 5:
            # Look for 4+ consecutive consonants (likely gibberish)
            for i in range(len(word) - 3):
                substring = word[i:i+4]
                if all(c not in 'aeiouAEIOU' for c in substring if c.isalpha()):
                    gibberish_count += 1
                    break

    if gibberish_count > 10:
        logger.debug(f"Text appears garbled ({gibberish_count} gibberish words)")
        return False

    # FORCE VISION EXTRACTION FOR TESTING
    logger.info("⚠️ Forcing vision extraction (test mode)")
    return False

    # logger.info("✅ Text quality sufficient for text-only extraction")
    # return True
