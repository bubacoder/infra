#!/usr/bin/env python3

import argparse
import os
import openai
import sys
import yaml
import logging
import traceback
import requests
import jwt
import time
import tiktoken
from pathlib import Path
from typing import Final, Optional, List, Tuple, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter, Language


class LLMTextProcessor(object):
    DEFAULT_MODEL_TYPE: Final[str] = "instruct"
    DEFAULT_ENCODING: Final[str] = "gpt-4o"
    DEFAULT_TEMPERATURE: Final[float] = 0.7

    def __init__(self):
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """Loads the configuration from a YAML file."""
        try:
            config_file_path = Path("config") / "config.yaml"
            with open(config_file_path, 'r') as file:
                config_data = yaml.safe_load(file)
            model_types = {m['type']: m for m in config_data['model_types']}
            endpoints = {e['name']: e for e in config_data['endpoints']}
            models = {m['name']: m for m in config_data['models']}
        except Exception as e:
            logging.error(f"Error reading config file: {e}")
            logging.debug(traceback.format_exc())
            sys.exit(1)

        for model in models.values():
            model['endpoint'] = endpoints.get(model['endpoint'])
            model.setdefault('context_length_tokens', -1)

        return {"model_types": model_types, "models": models}

    def get_template_names(self) -> List[str]:
        """Returns a list of YAML file names in the 'templates' folder without extension."""
        templates_dir = Path("templates")
        if not templates_dir.is_dir():
            logging.warning(f"Templates directory not found: {templates_dir}")
            return []

        template_files = templates_dir.glob("*.yaml")
        return [template.stem for template in template_files]

    def get_indexed_filename(self, filename: str, index: int) -> str:
        """Returns filename with an index appended before the extension."""
        base, ext = os.path.splitext(filename)
        return f"{base}_{index:03d}{ext}"

    def write_file(self, filename: str, text: str) -> None:
        """Writes text to the specified file."""
        with open(filename, "w") as output_file:
            output_file.write(text)

    def write_output(self, filename: str, chunk_count: int, index: int, text: str) -> None:
        """Writes output to an indexed file if there are multiple chunks."""
        output_filename = self.get_indexed_filename(filename, index) if chunk_count > 0 else filename
        self.write_file(output_filename, text)

    def write_outputs(self, filename_arg: Optional[str], chunks: List[str]) -> None:
        """Writes all chunks to output files if filename is specified."""
        if filename_arg:
            chunk_count = len(chunks)
            for i, chunk in enumerate(chunks, start=1):
                self.write_output(filename_arg, chunk_count, i, chunk)

    def jwt_seconds_to_expiration(self, token: str) -> int:
        """Calculates the seconds until JWT token expiration."""
        try:
            decoded_token = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256"])
            expiration_timestamp = decoded_token.get('exp')
            if expiration_timestamp is None:
                raise ValueError("The token does not contain an 'exp' claim.")
            return expiration_timestamp - time.time()
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    def count_tokens(self, text: str, encoding_name: str = 'gpt-4o') -> int:
        """Counts the number of tokens in the text using the specified encoding."""
        encoding = tiktoken.encoding_for_model(encoding_name)
        return len(encoding.encode(text))

    def split_language_into_chunks(self, text: str, max_tokens: int, language: Language) -> List[str]:
        """Splits markdown text into chunks using a recursive text splitter."""
        # No limit
        if max_tokens == -1:
            return [text]

        # Method1 - ONLY for markdown - headers stuck to previous text:
        # markdown_splitter = MarkdownTextSplitter(chunk_size=max_tokens, chunk_overlap=0)

        # Method2 - keep headers with document:
        markdown_splitter = RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=max_tokens * 4,  # TODO This requires characters. * 4 is a hack
            chunk_overlap=0
        )
        return [doc.page_content for doc in markdown_splitter.create_documents([text])]

    def load_prompt_parameters(self, template_arg: Optional[str], model_arg: Optional[str], temperature_arg: Optional[float]) -> Tuple[str, Dict]:
        """Loads prompt parameters from a YAML template file."""
        params = {}
        prompt_template = "<INPUT>"

        if template_arg:
            try:
                template_file_path = Path("templates") / f"{template_arg}.yaml"
                with open(template_file_path, 'r') as file:
                    template_data = yaml.safe_load(file)
                    params = template_data['params']
                    prompt_template = template_data['prompt']
            except Exception as e:
                logging.error(f"Error reading template file: {e}")
                logging.debug(traceback.format_exc())
                sys.exit(1)

        # Set defaults if not given
        params.setdefault('model_type', self.DEFAULT_MODEL_TYPE)
        params.setdefault('temperature', self.DEFAULT_TEMPERATURE)
        params.setdefault('chunking', 'disabled')

        # Override model if given
        if model_arg: params['model'] = model_arg
        if temperature_arg: params['temperature'] = float(temperature_arg)

        logging.debug(f"Prompt parameters: {params}")
        return prompt_template, params

    def get_input_chunks(self, input_text: str, chunking_mode: str = 'disabled', max_tokens: int = -1) -> List[str]:
        """Splits input text into chunks based on the chunking mode."""
        match chunking_mode:
            case 'disabled':
                return [input_text]
            case 'markdown-no-overlap':
                return self.split_language_into_chunks(input_text, max_tokens, Language.MARKDOWN)
            case 'python-no-overlap':
                return self.split_language_into_chunks(input_text, max_tokens, Language.PYTHON)
            case _:
                raise ValueError(f"Unsupported chunking mode: {chunking_mode}")

    def get_prompts(self, prompt_template: str, input_text_chunks: List[str]) -> List[str]:
        """Generates prompts by substituting <INPUT> in the template with input chunks."""
        return [prompt_template.replace("<INPUT>", chunk) for chunk in input_text_chunks]

    def get_response_from_openai_endpoint(self, prompt: str, model_config: Dict) -> str:
        """Gets a response from the OpenAI API."""
        client = openai.OpenAI(
            base_url=model_config["endpoint"]["url"],
            api_key=model_config["endpoint"]["api_key"],
        )
        response = client.chat.completions.create(
            model=model_config['name'],
            messages=[{"role": "user", "content": prompt}],
            temperature=model_config['temperature']
        )
        return response.choices[0].message.content.strip()

    def get_response_from_ollama_endpoint(self, prompt: str, model_config: Dict) -> str:
        """Gets a response from the Ollama API."""
        url = model_config["endpoint"]["url"]
        api_key = model_config["endpoint"]["api_key"]
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json'
        }

        data = {
            "prompt": prompt,
            "model": model_config['name'],
            "temperature": model_config['temperature'],
            # How can I specify the context window size?
            # https://github.com/ollama/ollama/blob/main/docs/faq.md
            "options": {
                "num_ctx": 4096  # TODO
            }
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            return response_data.get("choices", [{}])[0].get("text", "").strip()
        else:
            logging.error(f"Error from Ollama API: {response.status_code} - {response.text}")
            raise Exception(f"Ollama API request failed with status {response.status_code}")

    def get_response_from_raw_endpoint(self, prompt: str, model_config: Dict) -> str:
        """Gets a response from a raw endpoint."""
        url = model_config["endpoint"]["url"]
        api_key = model_config["endpoint"]["api_key"]
        headers = model_config.get("endpoint", {}).get("additional_headers", [])
        headers.append({'Authorization': f"Bearer {api_key}"})

        jwt_remaining_seconds = self.jwt_seconds_to_expiration(api_key)
        if jwt_remaining_seconds <= 0:
            raise Exception("JWT token expired.")
        else:
            logging.debug(f"JWT token expires in {round(jwt_remaining_seconds / 60, 2)} minutes")

        data = {"messages": [{"role": "user", "content": prompt}], "stream": True}

        response = requests.post(url, json=data, headers=headers, verify=False)
        return response.text

    def get_response(self, prompt: str, model_config: Dict) -> str:
        """Gets the response from the appropriate API based on the endpoint protocol."""
        try:
            logging.debug(f"Using model: {model_config['name']}, prompt: {prompt[:50]}...")
            protocol = model_config['endpoint']['protocol']
            url = model_config['endpoint']['url']
            match protocol:
                case 'openai':
                    logging.debug(f"Using OpenAI endpoint: {url}")
                    return self.get_response_from_openai_endpoint(prompt, model_config)
                case 'ollama':
                    logging.debug(f"Using Ollama endpoint: {url}")
                    return self.get_response_from_ollama_endpoint(prompt, model_config)
                case 'raw':
                    logging.debug(f"Using RAW endpoint: {url}")
                    return self.get_response_from_raw_endpoint(prompt, model_config)
                case _:
                    raise ValueError(f"Unsupported endpoint protocol: {protocol}")
        except Exception as e:
            logging.error(f"Error: {e}")
            sys.exit(1)

    def show_stats(self, prompt: str, response: str, model_config: Dict) -> None:
        """Logs the statistics of the prompt and response."""
        encoding_name = model_config.get("encoding_name", self.DEFAULT_ENCODING)
        prompt_tokens = self.count_tokens(prompt, encoding_name)
        response_tokens = self.count_tokens(response, encoding_name)
        logging.debug(f"Prompt: {len(prompt)} chars, {prompt_tokens} tokens ({encoding_name} encoding); Response: {len(response)} chars, {response_tokens} tokens; sum: {len(prompt) + len(response)} chars\n---------")

    def get_model_config(self, params: Dict) -> Dict:
        """Gets the model configuration based on parameters and configuration."""
        if 'model' not in params:
            model_type = params['model_type']
            model_types_config = self.config['model_types']
            params['model'] = model_types_config[model_type]['models'][0]  # TODO first model is used

        selected_model_name = params['model']
        selected_model_config = self.config['models'][selected_model_name]
        selected_model_config['temperature'] = params['temperature']
        logging.debug(f"Selected model config: {selected_model_config}")
        return selected_model_config

    def respond(self,
                input_text: str,
                template: str,
                model: str,
                temperature: float,
                log_chunks_to: str = None,
                log_prompts_to: str = None,
                log_responses_to: str = None,
                stop_after: str = None) -> str:

        prompt_template, params = self.load_prompt_parameters(template, model, temperature)

        model_config = self.get_model_config(params)

        input_chunks = self.get_input_chunks(input_text, params['chunking'], model_config["context_length_tokens"])
        self.write_outputs(log_chunks_to, input_chunks)
        if stop_after == 'chunking': return None

        prompts = self.get_prompts(prompt_template, input_chunks)
        self.write_outputs(log_prompts_to, prompts)
        if stop_after == 'templating': return None

        chunk_count = len(prompts)
        if chunk_count > 0: logging.debug(f"Chunk count: {chunk_count}")

        responses = []
        for i, prompt in enumerate(prompts, start=1):
            response = self.get_response(prompt, model_config)
            responses.append(response)

            if logging.DEBUG >= logging.root.level:
                self.show_stats(prompt, response, model_config)

            if log_responses_to:
                self.write_output(log_responses_to, chunk_count, i, response)

        complete_response = '\n'.join(responses)
        return complete_response


# ----------------------------------------------------------------------


def setup_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send input text to LLM and get response.")
    parser.add_argument("-m", "--model", type=str, help="Model to use")
    parser.add_argument("-e", "--temperature", type=str, help="Model temperature")
    parser.add_argument("-f", "--file", type=str, help="Input file")
    parser.add_argument("-i", "--input", type=str, help="Input text - if no '--file' or '--input' is given, will be read from standard input")
    parser.add_argument("-t", "--template", type=str, help="Prompt template (YAML format)")
    parser.add_argument("-o", "--output", type=str, help="Output file - if provided, the response will be written to this file.")
    parser.add_argument("--log-chunks-to", metavar="FILENAME", type=str, help="Write input chunk(s) to file")
    parser.add_argument("--log-prompts-to", metavar="FILENAME", type=str, help="Write prompt(s) to file")
    parser.add_argument("--log-responses-to", metavar="FILENAME", type=str, help="Write response(s) to file")
    parser.add_argument("--stop-after", metavar="ACTION", choices=["chunking", "templating"], help="Stop after specified step - possible values: chunking, templating")
    parser.add_argument("--log-level", type=str, default="INFO", help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    return parser


def setup_logging(log_level: str = "INFO") -> None:
    # Convert log_level string to logging level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')
    logging.basicConfig(level=numeric_level, format="[%(levelname)s] %(message)s")
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_input(input_arg: Optional[str], file_arg: Optional[str]) -> str:
    """Gets the input text either from a string, a file, or stdin."""
    if input_arg:
        return input_arg.strip()
    elif file_arg:
        try:
            with open(file_arg, 'r') as file:
                return file.read().strip()
        except Exception as e:
            logging.error(f"Error reading file: {e}")
            sys.exit(1)
    else:
        return sys.stdin.read().strip()


# ----------------------------------------------------------------------


def main() -> None:
    """Main function to handle argument parsing and logic flow."""
    parser = setup_argument_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)

    input_text = get_input(args.input, args.file)

    processor = LLMTextProcessor()
    response = processor.respond(
        input_text,
        args.template,
        args.model,
        args.temperature,
        args.log_chunks_to,
        args.log_prompts_to,
        args.log_responses_to,
        args.stop_after)

    if response is not None:
        if args.output:
            processor.write_file(args.output, response)
        else:
            print(response)


if __name__ == "__main__":
    main()
