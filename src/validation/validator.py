"""Dataset validation with schema and business rule checks."""
from datetime import datetime, date
from loguru import logger

from src.state import Dataset

type ValidationResult = tuple[bool, list[str]]


class DatasetValidator:
    """Validate extracted tax datasets against schema and business rules."""

    def validate(self, dataset: Dataset) -> ValidationResult:
        """
        Validate dataset against schema and business rules.

        Args:
            dataset: Extracted dataset to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        # Check required fields
        required = [
            "taxYear", "annualizedAmountDue", "amountDueAtClosing",
            "county", "parcelNumber", "nextTaxPaymentDate",
            "followingTaxPaymentDate"
        ]

        for field in required:
            if field not in dataset or dataset[field] is None:
                errors.append(f"Missing required field: {field}")

        # Validate types and formats
        errors.extend(self._validate_tax_year(dataset))
        errors.extend(self._validate_amounts(dataset))
        errors.extend(self._validate_dates(dataset))
        errors.extend(self._validate_county(dataset))
        errors.extend(self._validate_parcel_number(dataset))

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(" Validation passed")
        else:
            logger.warning(f" Validation failed with {len(errors)} errors")
            for error in errors:
                logger.warning(f"  - {error}")

        return is_valid, errors

    def _validate_tax_year(self, dataset: Dataset) -> list[str]:
        """Validate tax year field."""
        errors = []

        if "taxYear" not in dataset or dataset["taxYear"] is None:
            return errors  # Already caught by required field check

        tax_year = dataset["taxYear"]

        if not isinstance(tax_year, str):
            errors.append("taxYear must be a string")
            return errors

        if not tax_year.isdigit() or len(tax_year) != 4:
            errors.append(f"taxYear must be a 4-digit year string, got: {tax_year}")
            return errors

        # Check reasonable range
        year = int(tax_year)
        current_year = datetime.now().year

        if year < 2000 or year > current_year + 2:
            errors.append(
                f"taxYear {year} is outside reasonable range (2000-{current_year + 2})"
            )

        return errors

    def _validate_amounts(self, dataset: Dataset) -> list[str]:
        """Validate tax amount fields."""
        errors = []

        # Validate annualizedAmountDue
        if "annualizedAmountDue" in dataset and dataset["annualizedAmountDue"] is not None:
            amount = dataset["annualizedAmountDue"]

            if not isinstance(amount, (int, float)):
                errors.append(f"annualizedAmountDue must be a number, got: {type(amount).__name__}")
            elif amount < 0:
                errors.append(f"annualizedAmountDue cannot be negative: {amount}")
            elif amount == 0:
                errors.append("annualizedAmountDue should not be zero (warning)")
            elif amount > 1_000_000:
                errors.append(f"annualizedAmountDue seems unusually high: ${amount:,.2f} (warning)")

        # Validate amountDueAtClosing
        if "amountDueAtClosing" in dataset and dataset["amountDueAtClosing"] is not None:
            amount = dataset["amountDueAtClosing"]

            if not isinstance(amount, (int, float)):
                errors.append(f"amountDueAtClosing must be a number, got: {type(amount).__name__}")
            elif amount < 0:
                errors.append(f"amountDueAtClosing cannot be negative: {amount}")

        # Cross-validate amounts
        if ("annualizedAmountDue" in dataset and
            "amountDueAtClosing" in dataset and
            dataset["annualizedAmountDue"] is not None and
            dataset["amountDueAtClosing"] is not None):

            annualized = dataset["annualizedAmountDue"]
            at_closing = dataset["amountDueAtClosing"]

            # Amount at closing can be higher if there are delinquent amounts
            # But warn if it's significantly higher (>2x)
            if at_closing > annualized * 2:
                errors.append(
                    f"amountDueAtClosing (${at_closing:,.2f}) is more than 2x "
                    f"annualizedAmountDue (${annualized:,.2f}) - may include delinquent taxes (warning)"
                )

        return errors

    def _validate_dates(self, dataset: Dataset) -> list[str]:
        """Validate payment date fields."""
        errors = []

        next_date_str = dataset.get("nextTaxPaymentDate")
        following_date_str = dataset.get("followingTaxPaymentDate")

        if not next_date_str or not following_date_str:
            return errors  # Already caught by required field check

        try:
            next_date = date.fromisoformat(next_date_str)
            following_date = date.fromisoformat(following_date_str)
            today = date.today()

            # Next date must be after today's date (per README requirement)
            if next_date <= today:
                errors.append(
                    f"nextTaxPaymentDate ({next_date}) must be after today ({today})"
                )

            # Following should be after next
            if following_date <= next_date:
                errors.append(
                    f"followingTaxPaymentDate ({following_date}) must be after "
                    f"nextTaxPaymentDate ({next_date})"
                )

            # Dates shouldn't be too far in the future (sanity check)
            max_future_date = date(today.year + 3, 12, 31)
            if following_date > max_future_date:
                errors.append(
                    f"followingTaxPaymentDate ({following_date}) is too far in the future"
                )

        except ValueError as e:
            errors.append(f"Invalid date format: {e}")

        return errors

    def _validate_county(self, dataset: Dataset) -> list[str]:
        """Validate county name field."""
        errors = []

        if "county" not in dataset or not dataset["county"]:
            return errors  # Already caught by required field check

        county = dataset["county"]

        if not isinstance(county, str):
            errors.append(f"county must be a string, got: {type(county).__name__}")
            return errors

        county = county.strip()

        # Check for county suffix (should not be present)
        if county.lower().endswith(" county") or county.lower().endswith(" parish"):
            errors.append(
                f"County should not include 'County/Parish' suffix. "
                f"Got: '{county}', expected: '{county.replace(' County', '').replace(' Parish', '')}'"
            )

        # Check minimum length
        if len(county) < 2:
            errors.append(f"County name too short: '{county}'")

        return errors

    def _validate_parcel_number(self, dataset: Dataset) -> list[str]:
        """Validate parcel number field."""
        errors = []

        if "parcelNumber" not in dataset or not dataset["parcelNumber"]:
            return errors  # Already caught by required field check

        parcel = dataset["parcelNumber"]

        if not isinstance(parcel, str):
            errors.append(f"parcelNumber must be a string, got: {type(parcel).__name__}")
            return errors

        parcel = parcel.strip()

        # Basic sanity checks
        if len(parcel) < 3:
            errors.append(f"parcelNumber seems too short: '{parcel}'")

        # Parcel numbers shouldn't look like addresses
        address_indicators = ['st', 'ave', 'rd', 'blvd', 'drive', 'street', 'avenue']
        parcel_lower = parcel.lower()
        if any(indicator in parcel_lower for indicator in address_indicators):
            errors.append(
                f"parcelNumber appears to be an address, not a parcel ID: '{parcel}'"
            )

        return errors
