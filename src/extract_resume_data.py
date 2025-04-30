import os
import csv
import json
import requests
import time
import re
import sys
from pathlib import Path

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

# Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "gemma3:4b"
# Directory names
RESUMES_DIR = "markdown_resumes"
DATA_DIR = "data"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Get the project root directory (one level up from script location)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Full paths using project root
RESUMES_PATH = os.path.join(PROJECT_ROOT, RESUMES_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, DATA_DIR)
OUTPUT_FILE = os.path.join(DATA_PATH, "resume_data.csv")

# Define CSV columns
COLUMNS = [
    "First Name",
    "Last Name",
    "Full Name",
    "Email Address", 
    "Phone Number (primary)",
    "Alternative Phone (mobile/secondary)",
    "Address",
    "City",
    "State/Province",
    "Country",
    "Zip/Postal Code",
    "Current Job Title",
    "Skills",
    "Education",
    "Experience",
    "Skills Match Score",
    "Education Match Score",
    "Experience Match Score",
    "Overall Score"
]

# Job requirements and scoring settings from environment variable
JOB_REQUIREMENTS = {}
try:
    job_requirements_json = os.environ.get("JOB_REQUIREMENTS")
    if job_requirements_json:
        JOB_REQUIREMENTS = json.loads(job_requirements_json)
        print(f"Loaded job requirements: {JOB_REQUIREMENTS['job_title']}")
except Exception as e:
    print(f"Warning: Failed to load job requirements: {e}")

# Model configuration from environment variable
MODEL_CONFIG = {
    "model_type": "ollama",
    "ollama_model": DEFAULT_MODEL,
    "api_key": "",
    "api_provider": "openai",
    "model_name": ""
}
try:
    model_config_json = os.environ.get("MODEL_CONFIG")
    if model_config_json:
        loaded_config = json.loads(model_config_json)
        # Update the config with values from environment
        MODEL_CONFIG.update(loaded_config)
        print(f"Loaded model configuration: {MODEL_CONFIG['model_type']}")
        if MODEL_CONFIG["model_type"] == "ollama":
            print(f"Using Ollama model: {MODEL_CONFIG['ollama_model']}")
        else:
            print(f"Using {MODEL_CONFIG['api_provider']} API with model: {MODEL_CONFIG['model_name']}")
except Exception as e:
    print(f"Warning: Failed to load model configuration: {e}")
    print("Falling back to default Ollama model")

def generate_prompt(resume_text):
    """Create a prompt for the LLM to extract information from a resume."""
    return f"""
You are an AI assistant tasked with extracting specific information from a resume.
Extract the following information from the text below. If you can't find a specific piece of information, respond with "NA".
Return ONLY a JSON object with the following keys and nothing else:

{{
  "First_Name": "",
  "Last_Name": "",
  "Full_Name": "",
  "Email_Address": "",
  "Phone_Number_primary": "",
  "Alternative_Phone": "",
  "Address": "",
  "City": "",
  "State_Province": "",
  "Country": "",
  "Zip_Postal_Code": "",
  "Current_Job_Title": "",
  "Skills": "",
  "Education": "",
  "Experience": ""
}}

RESUME TEXT:
{resume_text}
"""

def generate_scoring_prompt(resume_text, job_requirements):
    """Create a prompt for the LLM to score a resume against job requirements."""
    return f"""
You are an AI assistant tasked with evaluating how well a candidate's resume matches specific job requirements.
You'll provide three scores (1-100) and detailed explanations:

1. Skills Match Score (1-100): How well the candidate's skills align with both required and preferred skills.
2. Education Match Score (1-100): How well the candidate's education background meets the requirements.
3. Experience Match Score (1-100): How well the candidate's work experience matches the job requirements.

Job Requirements:
Job Title: {job_requirements.get('job_title', 'Not specified')}
Required Skills: {job_requirements.get('required_skills', 'Not specified')}
Preferred Skills: {job_requirements.get('preferred_skills', 'Not specified')}
Education Requirements: {job_requirements.get('education', 'Not specified')}
Experience Requirements: {job_requirements.get('experience', 'Not specified')}
Job Description: {job_requirements.get('job_description', 'Not specified')}

Resume Content:
{resume_text}

Evaluate the resume against these requirements and return ONLY a JSON object with the following format and nothing else:
{{
  "skills_score": 75,
  "skills_explanation": "Detailed explanation of skills match...",
  "education_score": 80, 
  "education_explanation": "Detailed explanation of education match...",
  "experience_score": 90,
  "experience_explanation": "Detailed explanation of experience match...",
  "overall_score": 82,
  "overall_explanation": "Summary of why this candidate received this overall score..."
}}

The overall score should be a weighted average based on the relative importance of skills, education, and experience.
"""

def query_openai(prompt, api_key, model_name="gpt-4", retries=MAX_RETRIES):
    """Send a query to OpenAI API and return the response with retry logic."""
    if not OPENAI_AVAILABLE:
        print("Error: OpenAI package not installed. Install with: pip install openai")
        return None
    
    if not api_key:
        print("Error: No OpenAI API key provided")
        return None
    
    for attempt in range(retries):
        try:
            # Configure the OpenAI client with the API key
            client = openai.OpenAI(api_key=api_key)
            
            # Call the API with the prompt
            response = client.chat.completions.create(
                model=model_name or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.2
            )
            
            # Extract the generated text from the response
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content.strip()
            else:
                print("Error: Empty response from OpenAI API")
                return None
        
        except Exception as e:
            print(f"Error querying OpenAI (attempt {attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Maximum retries exceeded")
                return None

def query_anthropic(prompt, api_key, model_name="claude-3-opus-20240229", retries=MAX_RETRIES):
    """Send a query to Anthropic's API and return the response with retry logic."""
    if not ANTHROPIC_AVAILABLE:
        print("Error: Anthropic package not installed. Install with: pip install anthropic")
        return None
    
    if not api_key:
        print("Error: No Anthropic API key provided")
        return None
    
    for attempt in range(retries):
        try:
            # Configure the Anthropic client with the API key
            client = anthropic.Anthropic(api_key=api_key)
            
            # Call the API with the prompt
            response = client.messages.create(
                model=model_name,
                max_tokens=2000,
                temperature=0.2,
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
            print(f"Error querying Anthropic (attempt {attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Maximum retries exceeded")
                return None

def query_generic_api(prompt, api_key, api_provider, model_name, retries=MAX_RETRIES):
    """Send a query to a generic API provider and return the response with retry logic."""
    if not api_key:
        print(f"Error: No API key provided for {api_provider}")
        return None
    
    for attempt in range(retries):
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
                "max_tokens": 2000,
                "temperature": 0.2
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
            print(f"Error using generic API for {api_provider} (attempt {attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Maximum retries exceeded")
                return None

def query_ollama(prompt, model=None, retries=MAX_RETRIES):
    """Send a query to the Ollama API and return the response with retry logic."""
    if model is None:
        model = MODEL_CONFIG["ollama_model"]
        
    for attempt in range(retries):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=120  # Default timeout
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception as e:
            print(f"Error querying Ollama (attempt {attempt+1}/{retries}): {str(e)}")
            if attempt < retries - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Maximum retries exceeded")
                return None

def query_llm(prompt, purpose="extract"):
    """Query the configured LLM (Ollama or cloud API) based on model configuration."""
    # Determine which model to use based on the configuration
    if MODEL_CONFIG["model_type"] == "ollama":
        # Use Ollama
        return query_ollama(prompt, MODEL_CONFIG["ollama_model"])
    else:
        # Use cloud API
        api_provider = MODEL_CONFIG["api_provider"]
        api_key = MODEL_CONFIG["api_key"]
        model_name = MODEL_CONFIG["model_name"]
        
        # No API key provided
        if not api_key:
            print(f"Warning: No API key provided for {api_provider}. Falling back to Ollama.")
            return query_ollama(prompt)
        
        # Choose the appropriate API provider
        if api_provider == "openai":
            response = query_openai(prompt, api_key, model_name)
        elif api_provider == "anthropic":
            response = query_anthropic(prompt, api_key, model_name)
        else:
            # Generic API fallback
            response = query_generic_api(prompt, api_key, api_provider, model_name)
        
        # If the API call failed, fall back to Ollama
        if not response:
            print(f"API query failed for {purpose}. Falling back to Ollama.")
            return query_ollama(prompt)
        
        return response

def clean_json_string(json_str):
    """Clean and normalize the JSON string for better parsing."""
    # Try to fix common issues with JSON strings
    
    # Remove markdown code block markers if present
    json_str = re.sub(r'```json|```', '', json_str).strip()
    
    # Remove any text before the opening brace or after the closing brace
    start_idx = json_str.find('{')
    end_idx = json_str.rfind('}')
    
    if start_idx != -1 and end_idx != -1:
        json_str = json_str[start_idx:end_idx+1]
    
    # Fix escaped quotes
    json_str = json_str.replace('\\"', '"')
    
    # Replace single quotes with double quotes (common LLM mistake)
    in_string = False
    result = []
    for char in json_str:
        if char == '"':
            in_string = not in_string
        if char == "'" and not in_string:
            char = '"'
        result.append(char)
    
    return ''.join(result)

def extract_json_from_response(response_text):
    """Extract the JSON object from the response text."""
    if not response_text:
        return None
        
    try:
        # First try to parse as is
        return json.loads(response_text)
    except json.JSONDecodeError:
        # If that fails, try to clean up the response
        try:
            cleaned_text = clean_json_string(response_text)
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON even after cleaning: {str(e)}")
            print(f"Response text (first 100 chars): {response_text[:100]}...")
            return None

def score_resume(resume_text, job_requirements):
    """Score a resume against job requirements using the configured LLM."""
    if not job_requirements or not job_requirements.get('score_candidates', False):
        # Return default scores if not scoring or missing requirements
        return {
            "Skills Match Score": "NA",
            "Education Match Score": "NA",
            "Experience Match Score": "NA",
            "Overall Score": "NA"
        }
    
    print(f"Scoring resume against job requirements")
    
    # Generate prompt for scoring
    prompt = generate_scoring_prompt(resume_text, job_requirements)
    response = query_llm(prompt, purpose="scoring")
    
    if not response:
        print("Failed to get scoring response from LLM")
        return {
            "Skills Match Score": "NA",
            "Education Match Score": "NA",
            "Experience Match Score": "NA",
            "Overall Score": "NA"
        }
    
    # Extract JSON from response
    data = extract_json_from_response(response)
    if not data:
        print("Failed to parse scoring response as JSON")
        return {
            "Skills Match Score": "NA",
            "Education Match Score": "NA",
            "Experience Match Score": "NA",
            "Overall Score": "NA"
        }
    
    # Get scores from the response
    skills_score = data.get("skills_score", "NA")
    education_score = data.get("education_score", "NA")
    experience_score = data.get("experience_score", "NA")
    overall_score = data.get("overall_score", "NA")
    
    # Print explanations for debugging
    print(f"Skills Score: {skills_score}/100")
    if "skills_explanation" in data:
        print(f"Skills Explanation: {data['skills_explanation'][:100]}...")
    
    print(f"Education Score: {education_score}/100")
    if "education_explanation" in data:
        print(f"Education Explanation: {data['education_explanation'][:100]}...")
    
    print(f"Experience Score: {experience_score}/100")
    if "experience_explanation" in data:
        print(f"Experience Explanation: {data['experience_explanation'][:100]}...")
    
    print(f"Overall Score: {overall_score}/100")
    if "overall_explanation" in data:
        print(f"Overall Explanation: {data['overall_explanation'][:100]}...")
    
    return {
        "Skills Match Score": skills_score,
        "Education Match Score": education_score,
        "Experience Match Score": experience_score,
        "Overall Score": overall_score
    }

def process_resume_file(file_path, job_requirements):
    """Process a single resume file and extract information using the configured LLM."""
    try:
        print(f"Processing: {file_path}")
        
        # Read the resume file
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            resume_text = f.read()
        
        # Generate prompt and query LLM
        prompt = generate_prompt(resume_text)
        response = query_llm(prompt, purpose="extract")
        
        if response:
            # Extract JSON from response
            data = extract_json_from_response(response)
            if data:
                # Get scoring data if job requirements provided
                scores = score_resume(resume_text, job_requirements)
                
                # Return data with keys matching CSV columns
                return {
                    "First Name": data.get("First_Name", "NA"),
                    "Last Name": data.get("Last_Name", "NA"),
                    "Full Name": data.get("Full_Name", "NA"),
                    "Email Address": data.get("Email_Address", "NA"),
                    "Phone Number (primary)": data.get("Phone_Number_primary", "NA"),
                    "Alternative Phone (mobile/secondary)": data.get("Alternative_Phone", "NA"),
                    "Address": data.get("Address", "NA"),
                    "City": data.get("City", "NA"),
                    "State/Province": data.get("State_Province", "NA"),
                    "Country": data.get("Country", "NA"),
                    "Zip/Postal Code": data.get("Zip_Postal_Code", "NA"),
                    "Current Job Title": data.get("Current_Job_Title", "NA"),
                    "Skills": data.get("Skills", "NA"),
                    "Education": data.get("Education", "NA"),
                    "Experience": data.get("Experience", "NA"),
                    "Skills Match Score": scores.get("Skills Match Score", "NA"),
                    "Education Match Score": scores.get("Education Match Score", "NA"),
                    "Experience Match Score": scores.get("Experience Match Score", "NA"),
                    "Overall Score": scores.get("Overall Score", "NA")
                }
            
        # If we reach here, something went wrong
        print(f"Failed to extract data from {file_path}")
        return {col: "NA" for col in COLUMNS}
    
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return {col: "NA" for col in COLUMNS}

def calculate_weighted_score(data, job_requirements):
    """Calculate weighted score based on the weighting factors."""
    if not job_requirements or not job_requirements.get('score_candidates', False):
        return "NA"

    # Get weights from job requirements
    skills_weight = job_requirements.get('skills_weight', 2)
    education_weight = job_requirements.get('education_weight', 2)
    experience_weight = job_requirements.get('experience_weight', 2)
    
    # Get scores
    skills_score = data.get("Skills Match Score", "NA")
    education_score = data.get("Education Match Score", "NA")
    experience_score = data.get("Experience Match Score", "NA")
    
    # Skip if any scores are NA
    if skills_score == "NA" or education_score == "NA" or experience_score == "NA":
        return "NA"
    
    # Convert to integers
    try:
        skills_score = int(skills_score)
        education_score = int(education_score)
        experience_score = int(experience_score)
    except (ValueError, TypeError):
        return "NA"
    
    # Calculate weighted score
    total_weight = skills_weight + education_weight + experience_weight
    weighted_score = (
        (skills_score * skills_weight) +
        (education_score * education_weight) +
        (experience_score * experience_weight)
    ) / total_weight
    
    return round(weighted_score, 1)

def check_ollama_availability():
    """Check if Ollama is available and the model is installed."""
    try:
        requests.get("http://localhost:11434/api/version", timeout=5)
        print("Connected to Ollama server successfully")
        
        # Check if model is available
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [model["name"] for model in response.json().get("models", [])]
            
            model_name = MODEL_CONFIG["ollama_model"]
            if model_name not in models:
                print(f"Warning: {model_name} model not found. Please run 'ollama pull {model_name}' first.")
                return False
            else:
                print(f"Found {model_name} model on the Ollama server")
                return True
        except Exception as e:
            print(f"Warning: Could not verify if model is available: {str(e)}")
            print("Continuing anyway...")
            return True
            
    except requests.exceptions.RequestException:
        print("Warning: Ollama server is not running. Please start it with 'ollama serve'.")
        return False

def main():
    start_time = time.time()
    
    # Ensure data directory exists
    os.makedirs(DATA_PATH, exist_ok=True)
    
    # Check model availability based on configuration
    using_api = MODEL_CONFIG["model_type"] == "api"
    ollama_available = True
    
    if using_api:
        # Check if API key is provided
        if not MODEL_CONFIG["api_key"]:
            print(f"Warning: No API key provided for {MODEL_CONFIG['api_provider']}.")
            print("Checking if Ollama is available as fallback...")
            ollama_available = check_ollama_availability()
            if not ollama_available:
                print("Error: No API key provided and Ollama is not available. Cannot proceed.")
                return
            else:
                print("Ollama is available as fallback if API calls fail.")
        else:
            print(f"Using {MODEL_CONFIG['api_provider']} API with model: {MODEL_CONFIG['model_name']}")
            # Still check Ollama as we might fall back to it
            ollama_available = check_ollama_availability()
            if not ollama_available:
                print("Warning: Ollama is not available as fallback if API calls fail.")
    else:
        # Using Ollama as primary, check if it's available
        ollama_available = check_ollama_availability()
        if not ollama_available:
            print("Error: Ollama is not available and no API configuration is provided. Cannot proceed.")
            return
    
    # Get all markdown files
    resume_files = list(Path(RESUMES_PATH).glob("*.md"))
    
    if not resume_files:
        print(f"No markdown files found in {RESUMES_PATH}")
        return
    
    total_files = len(resume_files)
    print(f"Found {total_files} resume files to process")
    
    # Print job requirements info if available
    if JOB_REQUIREMENTS and JOB_REQUIREMENTS.get('score_candidates', False):
        print("\nJob Requirements:")
        print(f"Job Title: {JOB_REQUIREMENTS.get('job_title', 'Not specified')}")
        print(f"Required Skills: {JOB_REQUIREMENTS.get('required_skills', 'Not specified')}")
        print(f"Preferred Skills: {JOB_REQUIREMENTS.get('preferred_skills', 'Not specified')}")
        print(f"Education: {JOB_REQUIREMENTS.get('education', 'Not specified')}")
        print(f"Experience: {JOB_REQUIREMENTS.get('experience', 'Not specified')}")
        print(f"Weighting - Skills: {JOB_REQUIREMENTS.get('skills_weight', 2)}, " +
              f"Education: {JOB_REQUIREMENTS.get('education_weight', 2)}, " +
              f"Experience: {JOB_REQUIREMENTS.get('experience_weight', 2)}\n")
    
    # Create backup of existing output file if it exists
    if os.path.exists(OUTPUT_FILE):
        backup_file = f"{OUTPUT_FILE}.{int(time.time())}.bak"
        try:
            # Use copy and then remove for more robust backup
            import shutil
            shutil.copy2(OUTPUT_FILE, backup_file)
            print(f"Created backup of existing output file: {backup_file}")
        except Exception as e:
            print(f"Warning: Could not create backup file: {str(e)}")
    
    # Process each resume file and collect data
    all_data = []
    success_count = 0
    
    for i, file_path in enumerate(resume_files, 1):
        print(f"[{i}/{total_files}] Processing: {file_path.name}")
        data = process_resume_file(file_path, JOB_REQUIREMENTS)
        
        if data and any(v != "NA" for v in data.values()):
            success_count += 1
            
        # Add filename for reference
        data["Filename"] = file_path.name
        
        # Calculate weighted score if required
        if JOB_REQUIREMENTS and JOB_REQUIREMENTS.get('score_candidates', False):
            data["Weighted Score"] = calculate_weighted_score(data, JOB_REQUIREMENTS)
        else:
            data["Weighted Score"] = "NA"
        
        all_data.append(data)
        
        # Add a small delay to avoid overwhelming the API or Ollama
        if i < total_files:
            time.sleep(1.0)  # Slightly longer delay for API calls
    
    # Write data to CSV
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS + ["Filename", "Weighted Score"])
        writer.writeheader()
        writer.writerows(all_data)
    
    elapsed_time = time.time() - start_time
    minutes, seconds = divmod(elapsed_time, 60)
    
    print(f"\nSummary:")
    print(f"Processed {total_files} files ({success_count} successful)")
    print(f"Time taken: {int(minutes)} minutes, {int(seconds)} seconds")
    print(f"Data saved to {OUTPUT_FILE}")
    
    # If scores were generated, print a ranking
    if JOB_REQUIREMENTS and JOB_REQUIREMENTS.get('score_candidates', False):
        print("\nTop Candidates by Weighted Score:")
        # Sort by weighted score, handling "NA" values
        scored_candidates = [d for d in all_data if d["Weighted Score"] != "NA"]
        if scored_candidates:
            ranked_candidates = sorted(
                scored_candidates, 
                key=lambda x: float(x["Weighted Score"]), 
                reverse=True
            )
            for rank, candidate in enumerate(ranked_candidates[:5], 1):
                print(f"{rank}. {candidate.get('Full Name', 'Unknown')} " +
                      f"(Score: {candidate['Weighted Score']}/100)")
        else:
            print("No candidates were successfully scored.")

if __name__ == "__main__":
    main()