#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import re

# Get the project root directory (one level up from script location)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Directory names
SRC_DIR = "src"
DATA_DIR = "data"
DEFAULT_INPUT_DIR = "markdown_resumes"
DEFAULT_OUTPUT_FILE = os.path.join(DATA_DIR, "resume_data.csv")

# Full paths using project root
SRC_PATH = os.path.join(PROJECT_ROOT, SRC_DIR)
TARGET_SCRIPT = os.path.join(SRC_PATH, "extract_resume_data.py")

def main():
    # Define command line arguments
    parser = argparse.ArgumentParser(description='Run the resume data extractor with custom options')
    parser.add_argument('--model', default='gemma3:4b', help='Ollama model to use (default: gemma3:4b)')
    parser.add_argument('--input-dir', default=DEFAULT_INPUT_DIR, help=f'Directory containing resume markdown files (default: {DEFAULT_INPUT_DIR})')
    parser.add_argument('--output-file', default=DEFAULT_OUTPUT_FILE, help=f'Output CSV file path (default: {DEFAULT_OUTPUT_FILE})')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum number of retries for failed API calls (default: 3)')
    parser.add_argument('--retry-delay', type=int, default=2, help='Seconds to wait between retries (default: 2)')
    parser.add_argument('--timeout', type=int, default=120, help='Timeout for Ollama API calls in seconds (default: 120)')
    parser.add_argument('--check-ollama', action='store_true', help='Check if Ollama is running before starting')
    parser.add_argument('--install-deps', action='store_true', help='Install the requests dependency before running (basic check)')

    args = parser.parse_args()

    # Ensure input directory is an absolute path
    if not os.path.isabs(args.input_dir):
        args.input_dir = os.path.join(PROJECT_ROOT, args.input_dir)
    
    # Ensure output file is an absolute path
    if not os.path.isabs(args.output_file):
        args.output_file = os.path.join(PROJECT_ROOT, args.output_file)

    # Install dependencies if requested
    if args.install_deps:
        try:
            print("Checking/installing required packages...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        except subprocess.CalledProcessError:
            print("Warning: Failed to install dependencies. The script may fail if they're not installed.")

    # Check if Ollama is running
    if args.check_ollama:
        try:
            import requests
            print("Checking if Ollama is running...")
            response = requests.get("http://localhost:11434/api/version", timeout=5)
            if response.status_code == 200:
                print("Ollama is running")
            else:
                print("Ollama is not responding correctly", file=sys.stderr)
                print("You might need to start it with 'ollama serve' in another terminal.")
                proceed = input("Continue anyway? (y/n): ")
                if proceed.lower() != 'y':
                    return 1
        except Exception as e:
            print(f"Warning: Ollama server doesn't appear to be running: {e}")
            print("Please start Ollama with 'ollama serve' first")
            proceed = input("Continue anyway? (y/n): ")
            if proceed.lower() != 'y':
                return 1

    # Check if input directory exists
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist", file=sys.stderr)
        return 1

    # Ensure data directory exists for output file
    output_dir = os.path.dirname(args.output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Modify the extract_resume_data.py file with the custom options
    try:
        # Read the target script
        if not os.path.exists(TARGET_SCRIPT):
            print(f"Error: Target script '{TARGET_SCRIPT}' not found.", file=sys.stderr)
            return 1

        with open(TARGET_SCRIPT, 'r') as f:
            code = f.read()

        # Create a modified version with the new parameters
        # Prepare replacement values
        replacements = {
            'MODEL = "gemma3:4b"': f'MODEL = "{args.model}"',
            'RESUMES_DIR = "markdown_resumes"': f'RESUMES_DIR = "{args.input_dir}"',
            'MAX_RETRIES = 3': f'MAX_RETRIES = {args.max_retries}',
            'RETRY_DELAY = 2': f'RETRY_DELAY = {args.retry_delay}'
        }
        
        # Apply replacements
        for old, new in replacements.items():
            code = code.replace(old, new)
        
        # Replace OUTPUT_FILE with full path
        code = re.sub(r'OUTPUT_FILE = os\.path\.join\(DATA_PATH, "resume_data\.csv"\)',
                     f'OUTPUT_FILE = "{args.output_file}"', code)
        
        # Update timeout parameter in requests
        code = re.sub(r'timeout=\d+', f'timeout={args.timeout}', code)

        # Write temporary file
        temp_file = os.path.join(SRC_PATH, 'extract_resume_data_temp.py')
        with open(temp_file, 'w') as f:
            f.write(code)

        # Run the modified script
        print(f"Running resume data extractor with custom options...")
        python_executable = sys.executable
        result = subprocess.call([python_executable, temp_file])

        # Clean up
        os.remove(temp_file)

        return result
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        # Clean up temp file on error too
        if 'temp_file' in locals() and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass # Ignore cleanup error
        return 1

if __name__ == "__main__":
    sys.exit(main())