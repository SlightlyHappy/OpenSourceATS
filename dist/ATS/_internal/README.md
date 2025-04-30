# ATS - Applicant Tracking System

## Packaging and Distribution

This application has been packaged as a standalone Windows application that includes all dependencies. 

### How to Build the Package

If you're the developer who wants to create the distributable package:

1. Ensure you have Python installed on your system
2. Run the `Build_Package.bat` script
3. Wait for the build process to complete (may take several minutes)
4. The complete packaged application will be in the `dist` folder

### How to Distribute the Application

To distribute the application to other Windows users:

1. Copy the entire `dist/ATS` folder to a ZIP file or other distribution method
2. Include the `Start_ATS.bat` file in the root of your distribution
3. Instruct users to extract all files and run `Start_ATS.bat`

### For End Users: How to Run the Application

1. Extract all files from the ZIP (if provided in a compressed format)
2. Double-click on `Start_ATS.bat`
3. The application will automatically:
   - Start the ATS application server
   - Open your default web browser to the application
   - Create any necessary folders if they don't exist

### Important Notes

- The application does not require Python to be installed on the end user's computer
- All dependencies are included in the package
- The first time you run the application, Windows may show a security warning - you'll need to select "Run anyway" or similar
- The application will create empty folders for data, resumes, and emails if they don't exist

### Requirements for End Users

- Windows operating system
- 4GB+ RAM recommended
- To use AI features with Ollama, users will need to download and install Ollama from ollama.com
- For cloud LLM services (OpenAI, Anthropic, etc.), users will need their own API keys

## Support

If you encounter any issues with the packaged application, please contact the developer.