#!/usr/bin/env python3

import fnmatch
import os
import argparse
import logging
from gen import LLMTextProcessor, setup_logging


def setup_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send input text to LLM and get response.")
    parser.add_argument("-m", "--model", type=str, help="Model to use")
    parser.add_argument("-t", "--template", type=str, help="Prompt template (YAML format)")
    parser.add_argument("--pattern", type=str, default="*", help="Filename pattern e.g. '*.md'")
    parser.add_argument("--source-folder", type=str, help="Source folder")
    parser.add_argument("--target-folder", type=str, help="Target folder")
    parser.add_argument("--log-level", type=str, default="INFO", help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    return parser


def find_files(folder: str, pattern: str):
    """Walk through the folder and its subfolders"""
    for root, dirs, files in os.walk(folder):
        for file in fnmatch.filter(files, pattern):
            yield os.path.join(root, file)


def main() -> None:
    """Main function to handle argument parsing and logic flow."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)

    processor = LLMTextProcessor()
    file_list = find_files(args.source_folder, args.pattern)

    if file_list:
        for file_path in file_list:
            logging.info(f"Processing {file_path} ...")

            with open(file_path, 'r') as file:
                input_text = file.read().strip()

            response = processor.respond(input_text, args.template, args.model)

            if response is not None:
                relative_path = os.path.relpath(file_path, args.source_folder)
                target_path = os.path.join(args.target_folder, relative_path)
                processor.write_file(target_path, response)
    else:
        logging.error("No files found.")


if __name__ == "__main__":
    main()
