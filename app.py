import os
import subprocess
import sys
import time
import json
import pandas as pd
import threading
import requests
import werkzeug
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, session
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)

# Define the base directory for scripts
SRC_DIR = "src"
DATA_DIR = "data"
EMAILS_DIR = "Emails"
RESUMES_DIR = "resumes"  # Define the resumes directory as a constant

# Define the scripts and their display names
SCRIPTS = {
    "markdown": {"file": os.path.join(SRC_DIR, "markdown.py"), "name": "1. Convert Resumes to Markdown"},
    "extract": {"file": os.path.join(SRC_DIR, "extract_resume_data.py"), "name": "2. Extract Data via Ollama", "uses_ollama": True},
    "standardize": {"file": os.path.join(SRC_DIR, "standardize_resume_data.py"), "name": "3. Standardize Data"},
    "generate_emails": {"file": os.path.join(SRC_DIR, "generate_emails.py"), "name": "4. Generate Emails via Ollama", "uses_ollama": True, "requires_company_info": True},
    "fix_encoding": {"file": os.path.join(SRC_DIR, "fix_encoding.py"), "name": "5. Fix Email Encoding"},
}

# Define the expected directories
DIRS = {
    "resumes": "resumes",
    "markdown_resumes": "markdown_resumes",
    "emails": EMAILS_DIR,
    "data": DATA_DIR,
}

# Define expected output files
FILES = {
    "raw_data": os.path.join(DATA_DIR, "resume_data.csv"),
    "formatted_data": os.path.join(DATA_DIR, "formatted_resume_data.csv"),
}

# Global variable to track script progress
script_progress = {
    "is_running": False,
    "current_script": None,
    "progress": 0,
    "output": [],
    "status": "idle"
}

# Global model configuration with defaults
default_model_config = {
    "model_type": "ollama",
    "ollama_model": "gemma3:4b",
    "api_key": "",
    "api_provider": "openai",
    "model_name": "",
    "status": None,
    "status_message": None
}

def check_prerequisites():
    """Check if required directories and files exist."""
    missing = []
    # Check directories
    for key, path in DIRS.items():
        if not os.path.isdir(path):
            missing.append(f"Directory missing: '{path}' (Required for several steps)")

    # Check files needed as input for later steps
    if not os.path.exists(FILES["raw_data"]):
         missing.append(f"File missing: '{FILES['raw_data']}' (Required for Step 3: Standardize)")
    if not os.path.exists(FILES["formatted_data"]):
         missing.append(f"File missing: '{FILES['formatted_data']}' (Required for Step 4: Generate Emails)")

    return missing

def run_script_async(script_key, job_requirements=None, company_info=None, model_config=None):
    """Run the script in a separate thread and update progress via websockets."""
    global script_progress
    
    script_info = SCRIPTS[script_key]
    script_file = script_info["file"]
    script_progress["is_running"] = True
    script_progress["current_script"] = script_info["name"]
    script_progress["progress"] = 0
    script_progress["output"] = []
    script_progress["status"] = "running"
    
    # Use the global model config if not explicitly provided
    if model_config is None and script_info.get("uses_ollama", False):
        # Get model config from session or use default
        model_config = session.get('model_config', default_model_config)
    
    # Emit initial status update
    socketio.emit('script_update', script_progress)
    
    try:
        # Run the script and capture output
        python_executable = sys.executable
        
        # Set up the process with job requirements as an environment variable if provided
        env = os.environ.copy()
        if job_requirements and script_key == "extract":
            env["JOB_REQUIREMENTS"] = json.dumps(job_requirements)
        if company_info and script_key == "generate_emails":
            env["COMPANY_INFO"] = json.dumps(company_info)
        if model_config and script_info.get("uses_ollama", False):
            env["MODEL_CONFIG"] = json.dumps(model_config)
        
        # Set up the process
        process = subprocess.Popen(
            [python_executable, script_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env
        )
        
        # Process output in real-time
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            # Check if using Ollama and contains progress information
            if script_info.get("uses_ollama", False) and "%" in line:
                try:
                    # Try to extract percentage from Ollama output
                    percent_text = line.split("%")[0].strip().split(" ")[-1]
                    percent = int(float(percent_text))
                    script_progress["progress"] = percent
                except (ValueError, IndexError):
                    # If extraction fails, increment progress slightly
                    script_progress["progress"] = min(script_progress["progress"] + 1, 95)
            else:
                # For non-percentage lines, increment progress slightly for feedback
                if script_progress["progress"] < 95:
                    script_progress["progress"] += 1
            
            # Add line to output buffer
            script_progress["output"].append(line.strip())
            
            # Emit update
            socketio.emit('script_update', script_progress)
            time.sleep(0.01)  # Small delay to avoid flooding the client
        
        # Process any error output
        for line in iter(process.stderr.readline, ''):
            if not line:
                break
            script_progress["output"].append("ERROR: " + line.strip())
            socketio.emit('script_update', script_progress)
            time.sleep(0.01)
        
        # Wait for process to complete
        process.wait()
        
        # Update final status
        script_progress["progress"] = 100
        script_progress["status"] = "success" if process.returncode == 0 else "error"
        script_progress["is_running"] = False
        socketio.emit('script_update', script_progress)
        
    except Exception as e:
        script_progress["output"].append(f"Error running script: {str(e)}")
        script_progress["status"] = "error"
        script_progress["is_running"] = False
        socketio.emit('script_update', script_progress)

def check_ollama_installed():
    """Check if Ollama is installed and available in the PATH."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def check_api_connection(api_provider, api_key, model_name):
    """Test the connection to the API provider."""
    try:
        # OpenAI API test
        if api_provider == "openai":
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                # Simple test query
                response = client.chat.completions.create(
                    model=model_name or "gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Hello, are you working?"}],
                    max_tokens=20
                )
                return True, "OpenAI API connection successful."
            except ImportError:
                return False, "OpenAI package not installed. Install with: pip install openai"
            except Exception as e:
                return False, f"OpenAI API error: {str(e)}"
        
        # Anthropic API test
        elif api_provider == "anthropic":
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                # Simple test query
                response = client.messages.create(
                    model=model_name or "claude-3-haiku-20240307",
                    max_tokens=20,
                    messages=[{"role": "user", "content": "Hello, are you working?"}]
                )
                return True, "Anthropic API connection successful."
            except ImportError:
                return False, "Anthropic package not installed. Install with: pip install anthropic"
            except Exception as e:
                return False, f"Anthropic API error: {str(e)}"
        
        # Azure OpenAI API test
        elif api_provider == "azure":
            # Azure requires additional configuration that would need to be collected
            return False, "Azure OpenAI API testing not implemented yet. Set up your configuration and try using it with a task."
        
        # Generic API test - just check if API key is provided
        else:
            if not api_key:
                return False, "No API key provided."
            return True, f"{api_provider} API configuration saved. Testing not available."
    
    except Exception as e:
        return False, f"Error testing API connection: {str(e)}"

@app.route('/')
def index():
    """Render the main page with buttons for each script."""
    prerequisites_status = check_prerequisites()
    # Check script existence
    scripts_status = {key: os.path.exists(info["file"]) for key, info in SCRIPTS.items()}
    
    # Get model configuration from session or use default
    model_config = session.get('model_config', default_model_config)
    
    return render_template('index.html', 
                           scripts=SCRIPTS, 
                           scripts_status=scripts_status, 
                           prerequisites_status=prerequisites_status,
                           model_config=model_config)

@app.route('/save_model_config', methods=['POST'])
def save_model_config():
    """Save the model configuration."""
    model_type = request.form.get('model_type', 'ollama')
    
    # Initialize the model config
    model_config = {
        "model_type": model_type,
        "ollama_model": request.form.get('ollama_model', 'gemma3:4b'),
        "api_key": request.form.get('api_key', ''),
        "api_provider": request.form.get('api_provider', 'openai'),
        "model_name": request.form.get('model_name', '')
    }
    
    # Validate configuration
    if model_type == 'ollama':
        # Check if Ollama is installed
        if not check_ollama_installed():
            model_config["status"] = "error"
            model_config["status_message"] = "Ollama not installed or not available. Download from ollama.com."
            flash("Warning: Ollama not installed or not available. Download from ollama.com.", "error")
        else:
            model_config["status"] = "ok"
            model_config["status_message"] = "Ollama available"
    else:
        # API validation
        if not model_config["api_key"]:
            flash("Warning: No API key provided for cloud model. Please add your API key.", "error")
            model_config["status"] = "error"
            model_config["status_message"] = "No API key provided"
        else:
            # Don't test API here to avoid blocking - just save the configuration
            model_config["status"] = "ok"
            model_config["status_message"] = f"{model_config['api_provider']} API configured"
    
    # Save model configuration in session
    session['model_config'] = model_config
    
    flash(f"Model configuration saved successfully.", "success")
    return redirect(url_for('index'))

@app.route('/test_model_config', methods=['POST'])
def test_model_config():
    """Test the model configuration."""
    model_type = request.form.get('model_type', 'ollama')
    
    if model_type == 'ollama':
        # Check if Ollama is installed
        if not check_ollama_installed():
            return jsonify({
                'success': False,
                'message': 'Ollama not installed or not available. Download from ollama.com.'
            })
        
        # Check if model is available (optional - can be slow)
        model_name = request.form.get('ollama_model', 'gemma3:4b')
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if model_name not in result.stdout:
                return jsonify({
                    'success': False,
                    'message': f'Model {model_name} not available in Ollama. Try running: ollama pull {model_name}'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error checking Ollama models: {str(e)}'
            })
        
        return jsonify({
            'success': True,
            'message': f'Ollama is working and model {model_name} is available.'
        })
    else:
        # Test API connection
        api_key = request.form.get('api_key', '')
        api_provider = request.form.get('api_provider', 'openai')
        model_name = request.form.get('model_name', '')
        
        if not api_key:
            return jsonify({
                'success': False,
                'message': 'No API key provided.'
            })
        
        success, message = check_api_connection(api_provider, api_key, model_name)
        return jsonify({
            'success': success,
            'message': message
        })

@app.route('/job_requirements', methods=['GET', 'POST'])
def job_requirements():
    """Page for entering job requirements before extracting resume data."""
    if request.method == 'POST':
        requirements = {
            'job_title': request.form.get('job_title', ''),
            'required_skills': request.form.get('required_skills', ''),
            'preferred_skills': request.form.get('preferred_skills', ''),
            'education': request.form.get('education', ''),
            'experience': request.form.get('experience', ''),
            'job_description': request.form.get('job_description', ''),
            'skills_weight': int(request.form.get('skills_weight', 2)),
            'education_weight': int(request.form.get('education_weight', 2)),
            'experience_weight': int(request.form.get('experience_weight', 2)),
            'score_candidates': True  # Flag to indicate we want to score candidates
        }
        # Save requirements in session
        session['job_requirements'] = requirements
        
        # Start the extract script with the requirements
        if script_progress["is_running"]:
            flash(f"Another script is already running: {script_progress['current_script']}", "error")
            return redirect(url_for('job_requirements'))
        
        # Start script in a separate thread
        threading.Thread(target=run_script_async, args=("extract", requirements)).start()
        
        # Redirect to the progress page
        return redirect(url_for('progress'))
    
    # For GET request, show the form
    return render_template('job_requirements.html')

@app.route('/company_info', methods=['GET', 'POST'])
def company_info():
    """Page for entering company information before generating emails."""
    if request.method == 'POST':
        company_info = {
            'company_name': request.form.get('company_name', 'Bear Systems'),
            'job_position': request.form.get('job_position', 'Business Associate'),
            'compensation_model': request.form.get('compensation_model', '70% profit-sharing approach and self-directed schedule'),
            'sign_off': request.form.get('sign_off', 'Recruitment Team, Bear Systems'),
            'currency': request.form.get('currency', 'INR')
        }
        
        # Get model configuration from session
        model_config = session.get('model_config', default_model_config)
        
        # Save company info in session
        session['company_info'] = company_info
        
        # Start the generate_emails script with the company info and model config
        if script_progress["is_running"]:
            flash(f"Another script is already running: {script_progress['current_script']}", "error")
            return redirect(url_for('company_info'))
        
        # Start script in a separate thread
        threading.Thread(target=run_script_async, args=("generate_emails", None, company_info, model_config)).start()
        
        # Redirect to the progress page
        return redirect(url_for('progress'))
    
    # For GET request, show the form
    return render_template('company_info.html')

@app.route('/run/<script_key>', methods=['POST'])
def run_script(script_key):
    """Run the selected script asynchronously and redirect to the progress page."""
    global script_progress
    
    if script_key not in SCRIPTS:
        flash(f"Invalid script key: {script_key}", "error")
        return redirect(url_for('index'))

    script_info = SCRIPTS[script_key]
    script_file = script_info["file"]

    if not os.path.exists(script_file):
        flash(f"Script file not found: {script_file}", "error")
        return redirect(url_for('index'))
    
    if script_progress["is_running"]:
        flash(f"Another script is already running: {script_progress['current_script']}", "error")
        return redirect(url_for('index'))
    
    # For extract script, redirect to job requirements page
    if script_key == "extract":
        return redirect(url_for('job_requirements'))
    
    # For generate_emails script, redirect to company info page
    if script_key == "generate_emails":
        return redirect(url_for('company_info'))
    
    # Get model configuration from session if the script uses LLM
    model_config = None
    if script_info.get("uses_ollama", False):
        model_config = session.get('model_config', default_model_config)
        
        # Validate model configuration
        if model_config["model_type"] == "api" and not model_config["api_key"]:
            flash(f"API key is required for {script_info['name']} when using cloud model.", "error")
            return redirect(url_for('index'))
    
    # Start script in a separate thread
    threading.Thread(target=run_script_async, args=(script_key, None, None, model_config)).start()
    
    # Redirect to the progress page
    return redirect(url_for('progress'))

@app.route('/progress')
def progress():
    """Show the progress page with real-time updates."""
    return render_template('progress.html', script_name=script_progress.get("current_script", "Script"))

@app.route('/get_progress')
def get_progress():
    """API endpoint to get the current progress."""
    return jsonify(script_progress)

@app.route('/view_csv')
def view_csv():
    """View CSV data from the data directory."""
    csv_files = []
    for file in os.listdir(DATA_DIR):
        if file.endswith('.csv'):
            csv_files.append(file)
    
    selected_file = request.args.get('file', '')
    if selected_file and selected_file in csv_files:
        file_path = os.path.join(DATA_DIR, selected_file)
        try:
            df = pd.read_csv(file_path)
            columns = df.columns.tolist()
            data = df.to_dict('records')
            return render_template('view_csv.html', csv_files=csv_files, selected_file=selected_file, 
                                  columns=columns, data=data, error=None)
        except Exception as e:
            return render_template('view_csv.html', csv_files=csv_files, selected_file=selected_file, 
                                  columns=[], data=[], error=str(e))
    
    return render_template('view_csv.html', csv_files=csv_files, selected_file='', columns=[], data=[], error=None)

@app.route('/browse_emails')
def browse_emails():
    """Browse through generated emails."""
    email_files = []
    for file in os.listdir(EMAILS_DIR):
        if file.endswith('.txt') or file.endswith('.html'):
            email_files.append(file)
    
    selected_file = request.args.get('file', '')
    content = None
    
    if selected_file and selected_file in email_files:
        file_path = os.path.join(EMAILS_DIR, selected_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            flash(f"Error reading email file: {str(e)}", "error")
    
    return render_template('browse_emails.html', email_files=email_files, selected_file=selected_file, content=content)

@app.route('/download_email/<filename>')
def download_email(filename):
    """Download an email file."""
    return send_from_directory(os.path.abspath(EMAILS_DIR), filename, as_attachment=True)

@app.route('/upload_resumes', methods=['POST'])
def upload_resumes():
    """Handle resume file uploads."""
    try:
        # Check if the post request has the file part
        if 'resumeFiles' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file part in the request'
            })
        
        files = request.files.getlist('resumeFiles')
        
        # If no files selected
        if not files or files[0].filename == '':
            return jsonify({
                'success': False,
                'message': 'No files selected'
            })
        
        # Create resumes directory if it doesn't exist
        os.makedirs(RESUMES_DIR, exist_ok=True)
        
        # Process and save each file
        saved_files = []
        for file in files:
            if file:
                # Check file extension
                filename = werkzeug.utils.secure_filename(file.filename)
                extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                
                if extension not in ['pdf', 'doc', 'docx']:
                    return jsonify({
                        'success': False,
                        'message': f'Invalid file type for {filename}. Only PDF, DOC and DOCX files are allowed.'
                    })
                
                # Save the file to the resumes directory
                file_path = os.path.join(RESUMES_DIR, filename)
                file.save(file_path)
                saved_files.append(filename)
        
        # Flash message for the user
        flash(f"Successfully uploaded {len(saved_files)} resume(s): {', '.join(saved_files)}", "success")
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {len(saved_files)} resume(s)',
            'files': saved_files
        })
    
    except Exception as e:
        # Log the error
        print(f"Error uploading files: {str(e)}")
        
        return jsonify({
            'success': False,
            'message': f'Error uploading files: {str(e)}'
        })

if __name__ == '__main__':
    # Create required directories if they don't exist
    for path in DIRS.values():
        os.makedirs(path, exist_ok=True)
    # Ensure src directory exists for scripts
    os.makedirs(SRC_DIR, exist_ok=True)
    # Create __init__.py if it doesn't exist
    init_path = os.path.join(SRC_DIR, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, 'w') as f:
            pass # Create empty file

    print(f"Flask app running on http://127.0.0.1:5000")
    socketio.run(app, debug=True)  # Using socketio instead of app.run()