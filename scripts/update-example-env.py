#!/usr/bin/env python3
"""Mask sensitive variables in environment files for safe sharing.

This script reads an environment file and replaces sensitive values with
placeholder values, making it safe to share as an example configuration.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SENSITIVE_VARS_TO_MASK: tuple[str, ...] = (
    "KEY",
    "USERNAME",
    "PASSWORD",
    "PASSPHRASE",
    "TOKEN",
    "SECRET",
    "SENSITIVE",
)

SENSITIVE_VARS_TO_GENERALIZE: dict[str, str] = {
    "TIMEZONE": "Etc/UTC",
    "MYDOMAIN": "example.com",
    "LOCATION_CITY": "Greenwich",
    "LOCATION_LATITUDE": "51.48",
    "LOCATION_LONGITUDE": "0.00",
    "ADMIN_USER": "admin",
    "ADMIN_EMAIL": "root@localhost",
    "ADMIN_DISPLAYNAME": "AdminUser",
    "IP": "xxx.xxx.xxx.xxx",
}

MASKED_VALUE: str = '"use-some-very-secure-value-here"'


def contains_any_substring(string: str, substrings: tuple[str, ...]) -> bool:
    """Check if the string contains any of the given substrings."""
    return any(substring in string for substring in substrings)


def get_generalized_value(variable_name: str) -> str | None:
    """Find a generalized value for a variable if it matches a known pattern.

    Treats underscore as a word boundary, so SERVER_IP will match IP.
    Returns the generalized value if a match is found, None otherwise.
    """
    for key, value in SENSITIVE_VARS_TO_GENERALIZE.items():
        # Use custom boundaries: not preceded/followed by alphanumeric (treats _ as boundary)
        pattern = rf"(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])"
        if re.search(pattern, variable_name):
            return value
    return None


def mask_line(line: str) -> str:
    """Mask sensitive values in a single environment file line.

    Returns the processed line with sensitive values replaced.
    """
    if "=" not in line:
        return line.strip()

    variable, _ = line.strip().split("=", 1)
    variable = variable.strip()
    normalized_variable = variable.upper()
    generalized_value = get_generalized_value(normalized_variable)

    if generalized_value is not None:
        return f"{variable}={generalized_value}"

    if contains_any_substring(normalized_variable, SENSITIVE_VARS_TO_MASK):
        return f"{variable}={MASKED_VALUE}"

    return line.strip()


def mask_sensitive_variables(input_file: Path) -> str:
    """Read an environment file and mask all sensitive variables.

    Args:
        input_file: Path to the input environment file.

    Returns:
        The processed file content with sensitive values masked.
    """
    lines = input_file.read_text().splitlines()
    output_lines = [mask_line(line) for line in lines]
    return "\n".join(output_lines) + "\n"


def main() -> int:
    """Parse arguments and process the environment file."""
    parser = argparse.ArgumentParser(
        description="Mask sensitive variables in environment files for safe sharing.",
    )
    parser.add_argument("input_file", type=Path, help="Input environment file to process")
    parser.add_argument("output_file", type=Path, nargs="?", help="Output file (prints to stdout if not specified)")

    args = parser.parse_args()

    if not args.input_file.is_file():
        logger.error(f"Input file not found: {args.input_file}")
        return 1

    output = mask_sensitive_variables(args.input_file)

    if args.output_file:
        args.output_file.write_text(output)
    else:
        print(output, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
