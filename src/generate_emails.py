import csv
import os
import subprocess
import json
import time
import re
import shutil
import io
import unicodedata
import html
import sys
import requests

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

"""
Script to generate personalized emails for job candidates using LLM models.
Supports both local Ollama models and cloud-based API models (OpenAI, Anthropic).

This script:
1. Reads candidate data from formatted_resume_data.csv
2. Processes each row to generate a personalized email using the configured model
3. Saves the email to a text file in the Emails directory

Requirements:
- For local models: Ollama installed with gemma3:4b model available
- For cloud models: API keys for supported providers (OpenAI, Anthropic)
- formatted_resume_data.csv file with candidate information
"""

class ModelConfig:
    """Class to store model configuration for LLM usage."""
    def __init__(self):
        self.model_type = "ollama"  # Default to Ollama
        self.ollama_model = "gemma3:4b"  # Default Ollama model
        self.api_key = ""
        self.api_provider = "openai"
        self.model_name = ""
        
        # Try to load from environment variable if available
        self.load_from_env()
    
    def load_from_env(self):
        """Load model config from environment variable if available."""
        env_model_config = os.environ.get('MODEL_CONFIG')
        if env_model_config:
            try:
                data = json.loads(env_model_config)
                # Update attributes with values from environment
                if 'model_type' in data:
                    self.model_type = data['model_type']
                if 'ollama_model' in data:
                    self.ollama_model = data['ollama_model']
                if 'api_key' in data:
                    self.api_key = data['api_key']
                if 'api_provider' in data:
                    self.api_provider = data['api_provider']
                if 'model_name' in data:
                    self.model_name = data['model_name']
                print(f"Loaded model configuration from environment variable.")
            except json.JSONDecodeError:
                print("Warning: Failed to parse MODEL_CONFIG environment variable.")
            except Exception as e:
                print(f"Warning: Error loading model config from environment: {str(e)}")

class CompanyInfo:
    """Class to store company information for email generation."""
    def __init__(self):
        self.name = "Bear Systems"  # Default values
        self.job_position = "Business Associate"
        self.compensation_model = "70% profit-sharing approach and self-directed schedule"
        self.sign_off = "Recruitment Team, Bear Systems"
        self.currency = "INR"
        
        # Try to load from environment variable if available
        self.load_from_env()
    
    def load_from_env(self):
        """Load company info from environment variable if available."""
        env_company_info = os.environ.get('COMPANY_INFO')
        if env_company_info:
            try:
                data = json.loads(env_company_info)
                # Update attributes with values from environment
                if 'company_name' in data:
                    self.name = data['company_name']
                if 'job_position' in data:
                    self.job_position = data['job_position']
                if 'compensation_model' in data:
                    self.compensation_model = data['compensation_model']
                if 'sign_off' in data:
                    self.sign_off = data['sign_off']
                if 'currency' in data:
                    self.currency = data['currency']
                print(f"Loaded company information from environment variable.")
            except json.JSONDecodeError:
                print("Warning: Failed to parse COMPANY_INFO environment variable.")
            except Exception as e:
                print(f"Warning: Error loading company info from environment: {str(e)}")

# Directory names
EMAIL_DIR = "Emails"
DATA_DIR = "data"
# Get the project root directory (one level up from script location)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Full paths using project root
EMAIL_PATH = os.path.join(PROJECT_ROOT, EMAIL_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, DATA_DIR)
CSV_INPUT_FILE = os.path.join(DATA_PATH, "formatted_resume_data.csv")

# Create directory for emails if it doesn't exist
os.makedirs(EMAIL_PATH, exist_ok=True)

# Email template prompt
EMAIL_TEMPLATE = """
You are tasked with writing a personalized response email to a job applicant for the {job_position} position at {company_name}. The email should present an alternative compensation arrangement to a candidate whose background has caught your attention. The tone should be casual yet intriguing - not overtly selling the position but presenting it as a unique opportunity that might interest the right person. Below is the candidate's information.

Important guidelines:

1. Begin with a personalized greeting using their name.

2. Open with a brief acknowledgment of their application and mention that while reviewing applications, their background specifically caught your attention. Reference 1-2 specific elements from their profile that made them stand out (skills, experience, education, achievements).

3. Use subtle language that implies selectivity without stating it directly:
   - "We've been considering different approaches for certain candidates..."
   - "For select applicants with your background..."
   - "Not our standard arrangement, but for someone with your experience..."

4. Present the alternative compensation model casually but with subtle intrigue:
   - Explain the {compensation_model}
   - Frame it as "a different way of working that some of our most successful associates prefer"
   - Include a brief, matter-of-fact example of the earning potential without overselling it

5. Add a subtle hook that creates interest:
   - Mention briefly how someone with their specific background or skills could leverage this model
   - Include one subtle benefit that aligns with something in their profile (e.g., "gives you the flexibility to continue your work in [area of interest from their resume]")

6. Close with a casual but clear call to action that invites their thoughts:
   - "If this sounds like something that might work for you, I'd be happy to discuss it further."
   - "Would this kind of arrangement be of interest? Let me know your thoughts."

7. Sign off professionally but warmly as "{sign_off}"

The email should make the candidate feel specifically chosen for this alternative arrangement while maintaining a casual, non-desperate tone. It should pique their interest without coming across as too eager or salesy.

Candidate Information:
{candidate_info}

FORMAT YOUR RESPONSE LIKE THIS:
Subject: [Your subject line]

[Email Body]

IMPORTANT: Use only standard ASCII characters. Avoid special quotes, dashes, or other Unicode characters. AND ONLY USE {currency} Currency.
"""

def clean_text(text):
    """Clean text to ensure only standard ASCII characters are used."""
    # Common Unicode character mappings to ASCII
    unicode_mappings = {
        # Smart quotes and apostrophes
        '\u2018': "'", '\u2019': "'", '\u201a': "'", '\u201b': "'", 
        '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u201f': '"',
        # Dashes and hyphens
        '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-', 
        '\u2014': '--', '\u2015': '--', '\u2212': '-',
        # Spaces
        '\u00a0': ' ', '\u2000': ' ', '\u2001': ' ', '\u2002': ' ', 
        '\u2003': ' ', '\u2004': ' ', '\u2005': ' ', '\u2006': ' ', 
        '\u2007': ' ', '\u2008': ' ', '\u2009': ' ', '\u200a': ' ',
        # Other common characters
        '\u00ae': '(R)', '\u2122': '(TM)', '\u00a9': '(c)',
        '\u2026': '...', '\u00b0': ' degrees', '\u00b1': '+/-',
        '\u00d7': 'x', '\u00f7': '/',
        '\u20ac': 'EUR', '\u00a3': 'GBP', '\u00a5': 'JPY',
        '\u00a2': 'cents', '\u00b5': 'u', '\u00b6': 'p',
        '\u2022': '*', '\u2023': '>', '\u2043': '-',
        '\u204c': '>>', '\u204d': '<<', '\u2217': '*',
        # Accent mapping
        'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a', 'å': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o', 'ö': 'o', 'õ': 'o', 'ø': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ý': 'y', 'ÿ': 'y',
        'ñ': 'n', 'ç': 'c',
        # Additional problematic Unicode sequences
        "aEUR(TM)": "'", "aEUR\"": '"', "aEUR": "-", '\u2028': ' ', '\u2029': ' ',
    }
    
    # First try to decode any HTML entities
    text = html.unescape(text)
    
    # Replace known problematic patterns
    for orig, replacement in unicode_mappings.items():
        text = text.replace(orig, replacement)
    
    # Now handle any remaining non-ASCII by normalizing
    normalized = unicodedata.normalize('NFKD', text)
    result = ""
    
    for char in normalized:
        # If it's a combining character, skip it
        if unicodedata.combining(char):
            continue
        # If it's ASCII, keep it
        if ord(char) < 128:
            result += char
        # Otherwise replace with simple ASCII approximation
        else:
            # Try to find a good replacement
            if char in unicode_mappings:
                result += unicode_mappings[char]
            else:
                # For anything else, use a space instead of '?'
                result += ' '
    
    # Fix any specific known patterns that may remain
    result = result.replace("aEUR(TM)", "'")
    result = result.replace("aEUR\"", '"')
    result = result.replace("aEUR", "-")
    
    # Clean up excessive spaces
    result = re.sub(r'\s+', ' ', result)
    
    return result

def check_ollama_installed():
    """Check if Ollama is installed and available in the PATH."""
    return shutil.which("ollama") is not None

def check_model_available(model_name="gemma3:4b"):
    """Check if the specified model is available in Ollama."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return model_name in result.stdout
    except Exception:
        return False

def check_api_requirements(api_provider):
    """Check if required packages are installed for the specified API provider."""
    if api_provider == "openai":
        if not OPENAI_AVAILABLE:
            print("Warning: OpenAI package not installed. Run 'pip install openai' to use OpenAI API.")
            return False
        return True
    elif api_provider == "anthropic":
        if not ANTHROPIC_AVAILABLE:
            print("Warning: Anthropic package not installed. Run 'pip install anthropic' to use Anthropic API.")
            return False
        return True
    return True  # For other providers or when not checking specifically

def parse_email_response(response):
    """Parse the LLM response to extract subject and body."""
    # Remove any markdown formatting if present
    response = re.sub(r'```email\s+', '', response)
    response = re.sub(r'```\s*', '', response)
    
    # Try to find the subject line
    subject_match = re.search(r'(?:Subject:|SUBJECT:)\s*(.*?)(?:\n|$)', response, re.IGNORECASE)
    
    if subject_match:
        subject = subject_match.group(1).strip()
        # Get everything after the subject line
        subject_end_pos = subject_match.end()
        body = response[subject_end_pos:].strip()
        
        # If body starts with a newline, remove it
        if body.startswith('\n'):
            body = body[1:].strip()
    else:
        # If no subject found, try to extract a reasonable first line as subject
        lines = [line for line in response.split('\n') if line.strip()]
        if lines:
            subject = lines[0][:80]  # Use first line (truncated) as subject
            body = '\n'.join(lines[1:]) if len(lines) > 1 else "Thank you for your application to Bear Systems."
        else:
            subject = "Regarding Your Application to Bear Systems"
            body = response.strip() or "Thank you for your application to Bear Systems."
    
    return subject, body

def generate_email_openai(prompt, api_key, model_name="gpt-4"):
    """Generate email using OpenAI's API."""
    if not OPENAI_AVAILABLE:
        print("Error: OpenAI package not installed. Run 'pip install openai' to use OpenAI API.")
        return None
    
    try:
        # Configure the OpenAI client with the API key
        client = openai.OpenAI(api_key=api_key)
        
        # Call the API with the prompt
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Extract the generated text from the response
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        else:
            print("Error: Empty response from OpenAI API")
            return None
    
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return None

def generate_email_anthropic(prompt, api_key, model_name="claude-3-opus-20240229"):
    """Generate email using Anthropic's API."""
    if not ANTHROPIC_AVAILABLE:
        print("Error: Anthropic package not installed. Run 'pip install anthropic' to use Anthropic API.")
        return None
    
    try:
        # Configure the Anthropic client with the API key
        client = anthropic.Anthropic(api_key=api_key)
        
        # Call the API with the prompt
        response = client.messages.create(
            model=model_name,
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract the generated text from the response
        if response.content:
            # Extract text content from the response
            text_content = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_content)
        else:
            print("Error: Empty response from Anthropic API")
            return None
    
    except Exception as e:
        print(f"Error calling Anthropic API: {str(e)}")
        return None

def generate_email_generic_api(prompt, api_key, api_provider, model_name):
    """Fallback function for other API providers using simple requests."""
    try:
        # Generic implementation - this would need to be customized for specific providers
        print(f"Note: Using generic API implementation for {api_provider}. Limited functionality.")
        
        # This is a placeholder implementation and would need to be adjusted for specific APIs
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Placeholder request body - would need to be adjusted for specific APIs
        data = {
            "model": model_name,
            "prompt": prompt,
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        # Placeholder API endpoint - would need to be adjusted for specific APIs
        response = requests.post(
            f"https://api.{api_provider}.com/v1/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            # Generic extraction - assumes a structure similar to OpenAI's
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["text"].strip()
        
        print(f"Error: Failed to get response from {api_provider} API (Status {response.status_code})")
        print(response.text)
        return None
    
    except Exception as e:
        print(f"Error using generic API for {api_provider}: {str(e)}")
        return None

def generate_email_ollama(prompt, model_name="gemma3:4b"):
    """Generate email using local Ollama model."""
    try:
        # Write prompt to a temp file to avoid issues with input encoding
        temp_prompt_file = os.path.join(PROJECT_ROOT, f"temp_prompt_{int(time.time())}.txt")
        with open(temp_prompt_file, "w", encoding="utf-8") as f:
            f.write(prompt)
        
        # Use the file as input to Ollama
        result = subprocess.run(
            ["ollama", "run", model_name],
            stdin=open(temp_prompt_file, "r", encoding="utf-8"),
            capture_output=True,
            text=True,
            timeout=60  # Add timeout to prevent hanging
        )
        
        # Remove temp file
        try:
            os.remove(temp_prompt_file)
        except:
            pass
        
        # Check if command was successful
        if result.returncode != 0:
            print(f"Error running Ollama: {result.stderr}")
            return None
        
        # Extract the email content
        return result.stdout.strip()
    
    except subprocess.TimeoutExpired:
        print(f"Timeout while generating email with Ollama")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error generating email with Ollama: {e}")
        print(f"STDERR: {e.stderr}")
        return None
    except Exception as e:
        print(f"Unexpected error with Ollama: {str(e)}")
        return None

def generate_email_mock(row, company_info):
    """Generate a mock email for testing without any LLM model."""
    full_name = row.get("Full Name", "").strip()
    if not full_name and row.get("First Name") and row.get("Last Name"):
        full_name = f"{row['First Name']} {row['Last Name']}".strip()
    
    email_address = row.get("Email Address", "").strip()
    
    if not full_name or not email_address:
        return None
    
    subject = f"Regarding Your Application to {company_info.name} - {full_name}"
    body = f"""Hello {full_name},

Thank you for your application to {company_info.name}. We were particularly impressed by your background in {row.get('Current Job Title', 'your field')}.

We operate a bit differently at {company_info.name} - our associates get {company_info.compensation_model}. It's just how we do things here.

If this kind of arrangement interests you, let us know and we can discuss it further. This approach works well for some people, while others prefer traditional employment.

Best regards,
{company_info.sign_off}"""
    
    # Create the email file content
    email_file_content = f"{email_address}\n----------------\n{subject}\n----------------\n{body}"
    
    # Create filename based on full name
    safe_filename = full_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
    safe_filename = re.sub(r'[<>"|?*]', '_', safe_filename)  # Remove other invalid filename chars
    filename = os.path.join(EMAIL_PATH, f"{safe_filename}.txt")
    
    # Write to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(email_file_content)
    
    print(f"Mock email saved to: {filename}")
    return filename

def generate_email(row, company_info, model_config):
    """Generate a personalized email for a candidate using the configured model."""
    # Extract candidate info
    full_name = row.get("Full Name", "").strip()
    if not full_name and row.get("First Name") and row.get("Last Name"):
        full_name = f"{row['First Name']} {row['Last Name']}".strip()
    
    email_address = row.get("Email Address", "").strip()
    
    # Skip if no name or email
    if not full_name or not email_address:
        print(f"Skipping incomplete record: {row}")
        return None

    # Create candidate info block
    candidate_info = "\n".join([f"{key}: {value}" for key, value in row.items() if value and key != "Filename"])
    
    # Prepare prompt for LLM
    prompt = EMAIL_TEMPLATE.format(
        candidate_info=candidate_info,
        company_name=company_info.name,
        job_position=company_info.job_position,
        compensation_model=company_info.compensation_model,
        sign_off=company_info.sign_off,
        currency=company_info.currency
    )
    
    # Generate email content using the configured model
    print(f"Generating email for: {full_name}")
    email_content = None
    
    try:
        if model_config.model_type == "ollama":
            # Use Ollama
            email_content = generate_email_ollama(prompt, model_config.ollama_model)
        else:
            # Use API-based models
            if model_config.api_provider == "openai":
                email_content = generate_email_openai(prompt, model_config.api_key, model_config.model_name)
            elif model_config.api_provider == "anthropic":
                email_content = generate_email_anthropic(prompt, model_config.api_key, model_config.model_name)
            else:
                # Generic API fallback
                email_content = generate_email_generic_api(
                    prompt, model_config.api_key, model_config.api_provider, model_config.model_name
                )
        
        # If all model attempts failed, fall back to mock generation
        if not email_content:
            print(f"Model-based email generation failed for {full_name}. Falling back to mock email.")
            return generate_email_mock(row, company_info)
        
        # Parse the response
        subject, body = parse_email_response(email_content)
        
        # Clean the subject and body to ensure only ASCII characters
        subject = clean_text(subject)
        body = clean_text(body)
        
        # Update any references to the default company name in case the model didn't use the variables
        subject = subject.replace("Bear Systems", company_info.name)
        body = body.replace("Bear Systems", company_info.name)
        body = body.replace("Recruitment Team, Bear Systems", company_info.sign_off)
        
        # Create the email file content
        email_file_content = f"{email_address}\n----------------\n{subject}\n----------------\n{body}"
        
        # Create filename based on full name
        safe_filename = full_name.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_")
        safe_filename = re.sub(r'[<>"|?*]', '_', safe_filename)  # Remove other invalid filename chars
        filename = os.path.join(EMAIL_PATH, f"{safe_filename}.txt")
        
        # Write to file
        with open(filename, "w", encoding="utf-8") as f:
            f.write(email_file_content)
        
        print(f"Email saved to: {filename}")
        return filename
    
    except Exception as e:
        print(f"Unexpected error for {full_name}: {str(e)}")
        # Fall back to mock generation if anything fails
        print(f"Falling back to mock email for {full_name}")
        return generate_email_mock(row, company_info)

def main():
    """Main function to process the CSV and generate emails."""
    # Initialize company info with default values
    company_info = CompanyInfo()
    
    # Initialize model config with default values
    model_config = ModelConfig()
    
    # Only prompt for input if not running through the web interface
    if not os.environ.get('COMPANY_INFO'):
        # Get company information from user
        print("\n=== Company Information Setup ===")
        print("Enter information about the company and job (press Enter to use defaults)\n")
        
        company_name = input(f"Company name [{company_info.name}]: ").strip()
        if company_name:
            company_info.name = company_name
            
        job_position = input(f"Job position [{company_info.job_position}]: ").strip()
        if job_position:
            company_info.job_position = job_position
            
        compensation_model = input(f"Compensation model [{company_info.compensation_model}]: ").strip()
        if compensation_model:
            company_info.compensation_model = compensation_model
            
        sign_off = input(f"Email sign-off [{company_info.sign_off}]: ").strip()
        if sign_off:
            company_info.sign_off = sign_off
            
        currency = input(f"Currency to use in emails [{company_info.currency}]: ").strip()
        if currency:
            company_info.currency = currency
    else:
        # Running through the web interface, skip the prompts
        print("Running in web mode with provided company information.")
    
    print(f"\nUsing the following company information:")
    print(f"- Company name: {company_info.name}")
    print(f"- Job position: {company_info.job_position}")
    print(f"- Compensation model: {company_info.compensation_model}")
    print(f"- Email sign-off: {company_info.sign_off}")
    print(f"- Currency: {company_info.currency}")
    print("\n")
    
    # Display model configuration
    print(f"Using model configuration:")
    print(f"- Model type: {model_config.model_type}")
    
    use_mock = False
    
    if model_config.model_type == "ollama":
        print(f"- Ollama model: {model_config.ollama_model}")
        
        # Check if Ollama is installed
        if not check_ollama_installed():
            print("Warning: Ollama is not installed or not in PATH.")
            print("Visit https://ollama.com/download for installation instructions.")
            print("Falling back to mock email generation.")
            use_mock = True
        
        # Check if the model is available
        if not use_mock and not check_model_available(model_config.ollama_model):
            print(f"Warning: {model_config.ollama_model} model might not be available in Ollama.")
            print(f"Consider running 'ollama pull {model_config.ollama_model}' to download the model first.")
            proceed = input("Would you like to: \n1. Continue with Ollama anyway\n2. Use mock emails\n3. Exit\nEnter choice (1/2/3): ").strip()
            if proceed == '2':
                use_mock = True
            elif proceed != '1':
                print("Exiting.")
                return
    else:
        # API-based models
        print(f"- API Provider: {model_config.api_provider}")
        print(f"- Model name: {model_config.model_name}")
        
        # Check if API key is provided
        if not model_config.api_key:
            print(f"Warning: No API key provided for {model_config.api_provider}.")
            print("Falling back to mock email generation.")
            use_mock = True
        
        # Check if required packages are installed
        if not use_mock and not check_api_requirements(model_config.api_provider):
            proceed = input("Would you like to: \n1. Continue anyway\n2. Use mock emails\n3. Exit\nEnter choice (1/2/3): ").strip()
            if proceed == '2':
                use_mock = True
            elif proceed != '1':
                print("Exiting.")
                return
    
    # Read the CSV file
    csv_file = CSV_INPUT_FILE
    
    # Check if the CSV file exists
    if not os.path.exists(csv_file):
        print(f"Error: CSV file '{csv_file}' not found.")
        print(f"Please ensure you have run the 'standardize_resume_data.py' script first.")
        return
    
    processed = 0
    skipped = 0
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Add delay to not overwhelm API
                if processed > 0:
                    time.sleep(2)  # 2-second delay between requests
                
                if use_mock:
                    result = generate_email_mock(row, company_info)
                else:
                    result = generate_email(row, company_info, model_config)
                    
                if result:
                    processed += 1
                else:
                    skipped += 1
                
                # Add a progress indicator
                print(f"Progress: {processed + skipped} rows processed ({processed} emails generated, {skipped} skipped)")
        
        print(f"\nProcess completed. Generated {processed} emails, skipped {skipped} records.")
        print(f"Emails saved to the '{EMAIL_DIR}' directory.")
    
    except FileNotFoundError:
        print(f"Error: Could not open file '{csv_file}'")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        print(f"Partial results: Generated {processed} emails, skipped {skipped} records.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()