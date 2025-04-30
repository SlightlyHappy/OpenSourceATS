@echo off
echo Building ATS Application Package...
echo This may take a few minutes. Please wait...

:: Set up virtual environment
echo Setting up a virtual environment...
python -m venv venv
call venv\Scripts\activate

:: Install required packages
echo Installing required packages...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: Install additional packages explicitly needed for packaging
echo Installing additional dependencies for packaging...
pip install pyinstaller
pip install flask-socketio pandas werkzeug jinja2 engineio socketio bidict openai anthropic PyPDF2

:: Run PyInstaller with verbose output to see any issues
echo Building the package with PyInstaller...
pyinstaller ATS.spec --noconfirm --clean

:: Copy Start_ATS.bat to the dist folder
echo Copying startup files to distribution folder...
copy Start_ATS.bat dist\

:: Create a distribution ZIP file
echo Creating distribution ZIP file...
cd dist
powershell Compress-Archive -Path ATS, Start_ATS.bat -DestinationPath ATS_Distribution.zip -Force
cd ..

echo.
echo ==========================================
echo Build completed! 
echo.
echo The packaged application can be found in the "dist" folder.
echo A ZIP file for distribution has been created at: dist\ATS_Distribution.zip
echo.
echo To distribute the application:
echo 1. Share the ATS_Distribution.zip file
echo 2. Users should extract all files and run Start_ATS.bat
echo ==========================================
echo.
pause