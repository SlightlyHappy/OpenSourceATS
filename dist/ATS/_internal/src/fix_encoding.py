import os
import re

# Directory names
EMAIL_DIR = "Emails"
# Get the project root directory (one level up from script location)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Full paths using project root
EMAIL_PATH = os.path.join(PROJECT_ROOT, EMAIL_DIR)

def fix_encoding(file_path):
    """Fix encoding issues in the specified file."""
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Fix common encoding issues with regular expressions
        # Euro symbol issues
        content = re.sub(r'\u20AC\u201C', '--', content)  # Euro + quotation mark → dash
        content = re.sub(r'\u20AC\u2122', "'", content)   # Euro + trade mark → apostrophe
        
        # Other common encoding errors
        content = re.sub(r'â-', '-', content)            # Broken dash
        content = re.sub(r'â\'', "'", content)            # Broken apostrophe
        content = re.sub(r'â\'s', "'s", content)          # Broken possessive
        content = re.sub(r'â\'ve', "'ve", content)        # Broken 've
        content = re.sub(r'â\'re', "'re", content)        # Broken 're
        content = re.sub(r'â\'d', "'d", content)          # Broken 'd
        content = re.sub(r'â\'ll', "'ll", content)        # Broken 'll
        content = re.sub(r'â€"', '--', content)           # Broken em dash
        content = re.sub(r'â€™', "'", content)            # Broken apostrophe (another variant)
        content = re.sub(r'â€¦', '...', content)          # Broken ellipsis
        content = re.sub(r'â‚¹', '₹', content)          # Broken ellipsis
        
        # Write the fixed content back to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        
        print(f"Fixed encoding in {file_path}")
        return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    # Ensure the directory exists
    if not os.path.isdir(EMAIL_PATH):
        print(f"Warning: Email directory '{EMAIL_PATH}' not found. No files to fix.")
        return
    
    # Process each .txt file in the directory
    processed_count = 0
    for filename in os.listdir(EMAIL_PATH):
        if filename.endswith(".txt"):
            file_path = os.path.join(EMAIL_PATH, filename)
            if fix_encoding(file_path):
                processed_count += 1
    
    print(f"\nCompleted: Fixed encoding in {processed_count} files")

if __name__ == "__main__":
    main()