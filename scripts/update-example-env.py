#!/usr/bin/env python3
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
    'ADMIN_DISPLAYNAME': 'AdminUser'
}


def contains_any_substring(string: str, substrings: list[str]) -> bool:
    return any(substring in string for substring in substrings)


def mask_sensitive_variables(input_file: str) -> str:
    with open(input_file) as f:
        lines = f.readlines()

    output_lines = []
    for line in lines:
        if '=' in line:
            variable, value = line.strip().split('=', 1)
            if variable in SENSITIVE_VARS_TO_GENERALIZE:
                output_lines.append(f"{variable}={SENSITIVE_VARS_TO_GENERALIZE[variable]}")
            elif contains_any_substring(variable, SENSITIVE_VARS_TO_MASK):
                output_lines.append(f"{variable}=\"use-some-very-secure-value-here\"")
            else:
                output_lines.append(line.strip())
        else:
            output_lines.append(line.strip())

    return '\n'.join(output_lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: ./update-example-env.py <input_env_file>")
        return

    input_file = sys.argv[1]
    output = mask_sensitive_variables(input_file)
    print(output)


if __name__ == "__main__":
    main()
