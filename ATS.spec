import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the absolute path of the project directory
project_dir = os.path.abspath(os.getcwd())

# Collect data files from templates folder
template_files = [(os.path.join(project_dir, 'templates', f), 'templates') 
                 for f in os.listdir(os.path.join(project_dir, 'templates'))]

# Define all data folders to include
data_folders = [
    ('templates', 'templates'),
]

# Define empty folders to create in the bundle
empty_folders = ['data', 'Emails', 'markdown_resumes', 'resumes']

# Add src files
src_files = [(os.path.join(project_dir, 'src', f), 'src') 
             for f in os.listdir(os.path.join(project_dir, 'src'))]

# Collect all data files
datas = template_files + src_files
datas += [(os.path.join(project_dir, 'README.md'), '.')]
datas += [(os.path.join(project_dir, 'requirements.txt'), '.')]

# Comprehensive hidden imports for Flask and SocketIO
hidden_imports = [
    'flask',
    'flask_socketio',
    'engineio',
    'socketio',
    'engineio.async_drivers.threading',
    'werkzeug',
    'jinja2',
    'pandas',
    'requests',
    'json',
    'time',
    'threading',
    'os',
    'sys',
    'webbrowser',
    'subprocess',
    'bidict',
    'openai',
    'anthropic',
    'PyPDF2',
]

# Add all engineio and socketio submodules
hidden_imports += collect_submodules('engineio')
hidden_imports += collect_submodules('socketio')
hidden_imports += collect_submodules('flask_socketio')
hidden_imports += collect_submodules('werkzeug')
hidden_imports += collect_submodules('jinja2')

a = Analysis(
    ['launcher.py'],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create empty folders in the bundle
for folder in empty_folders:
    a.datas += [(os.path.join(folder, '.keep'), '', 'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ATS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ATS',
)