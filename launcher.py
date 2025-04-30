import os
import subprocess
import sys
import webbrowser
import threading
import time
import socket

# Function to check if a required module is available
def check_dependencies():
    missing_modules = []
    required_modules = [
        'flask', 'flask_socketio', 'pandas', 'werkzeug', 
        'requests', 'jinja2', 'engineio', 'socketio'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    return missing_modules

# Check dependencies first
missing_deps = check_dependencies()
if missing_deps:
    print("Error: Missing required Python dependencies:")
    for dep in missing_deps:
        print(f" - {dep}")
    print("\nAttempting to install missing dependencies...")
    
    # Try to install missing dependencies
    try:
        for dep in missing_deps:
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)
        print("Dependencies installed successfully. Starting application...")
    except Exception as e:
        print(f"Failed to install dependencies: {str(e)}")
        print("\nPlease manually install the following dependencies:")
        for dep in missing_deps:
            print(f"pip install {dep}")
        input("Press Enter to exit...")
        sys.exit(1)

# Add the current directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Import the Flask app
    from flask_socketio import SocketIO
    from app import app, socketio
except ImportError as e:
    print(f"Error importing application modules: {str(e)}")
    print("This might indicate an issue with the application packaging.")
    input("Press Enter to exit...")
    sys.exit(1)

# Function to check if port is available
def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

# Function to open browser after a delay
def open_browser():
    # Wait for server to start
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')

# Find an available port starting from 5000
port = 5000
while not is_port_available(port) and port < 6000:
    port += 1

if port >= 6000:
    print("Could not find an available port. Please close some applications and try again.")
    input("Press Enter to exit...")
    sys.exit(1)

# Start the Flask app
if __name__ == "__main__":
    print(f"Starting ATS application on http://127.0.0.1:{port}")
    print("The application window will open automatically in your default browser.")
    
    # Create required directories if they don't exist
    for path in ["data", "Emails", "markdown_resumes", "resumes"]:
        os.makedirs(os.path.join(current_dir, path), exist_ok=True)
    
    try:
        # Start a thread to open the browser
        threading.Thread(target=open_browser, daemon=True).start()
        
        # Run the Flask app
        socketio.run(app, host='127.0.0.1', port=port, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Error starting the application: {str(e)}")
        input("Press Enter to exit...")
        sys.exit(1)