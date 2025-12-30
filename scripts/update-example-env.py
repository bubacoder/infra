#!/usr/bin/env python3
import re
import sys

SENSITIVE_VARS_TO_MASK = [
    'KEY',
    'USERNAME',
    'PASSWORD',
    'PASSPHRASE',
    'TOKEN',
    'SECRET',
    'SENSITIVE',
]

SENSITIVE_VARS_TO_GENERALIZE = {
    'TIMEZONE': 'Etc/UTC',
    'MYDOMAIN': 'example.com',
    'LOCATION_CITY': 'Greenwich',
    'LOCATION_LATITUDE': '51.48',
    'LOCATION_LONGITUDE': '0.00',
    'ADMIN_USER': 'admin',
    'ADMIN_EMAIL': 'root@localhost',
    'ADMIN_DISPLAYNAME': 'AdminUser',
    'IP': 'xxx.xxx.xxx.xxx'
}


def contains_any_substring(string: str, substrings: list[str]) -> bool:
    return any(substring in string for substring in substrings)


def get_generalized_value(variable_name: str) -> str | None:
    """Check if any generalization key appears as a discrete word in the variable name.

    Treats underscore as a word boundary, so SERVER_IP will match IP.
    Returns the generalized value if a match is found, None otherwise.
    """
    for key, value in SENSITIVE_VARS_TO_GENERALIZE.items():
        # Use custom boundaries: not preceded/followed by alphanumeric (treats _ as boundary)
        pattern = rf'(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])'
        if re.search(pattern, variable_name):
            return value
    return None


def mask_sensitive_variables(input_file: str) -> str:
    with open(input_file) as f:
        lines = f.readlines()

    output_lines = []
    for line in lines:
        if '=' in line:
            variable, value = line.strip().split('=', 1)
            generalized_value = get_generalized_value(variable)
            if generalized_value is not None:
                output_lines.append(f"{variable}={generalized_value}")
            elif contains_any_substring(variable, SENSITIVE_VARS_TO_MASK):
                output_lines.append(f"{variable}=\"use-some-very-secure-value-here\"")
            else:
                output_lines.append(line.strip())
        else:
            output_lines.append(line.strip())

    return '\n'.join(output_lines) + '\n'


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: ./update-example-env.py <input_env_file> [output_env_file]")
        return

    input_file = sys.argv[1]
    output = mask_sensitive_variables(input_file)

    if len(sys.argv) == 3:
        output_file = sys.argv[2]
        with open(output_file, 'w') as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
