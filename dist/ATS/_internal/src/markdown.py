import os
import sys
import re
import PyPDF2
import docx
from pathlib import Path
import io
import chardet
import subprocess
import tempfile
import time
import fitz  # PyMuPDF for better PDF text extraction

# Fix console encoding for Windows
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding for the console
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)  # Set UTF-8 code page
    except Exception:
        # If that fails, we'll use ASCII fallbacks
        pass

# Define status symbols with ASCII fallbacks
CHECK_MARK = "✓" if sys.stdout.encoding.lower() == 'utf-8' else "+"
WARNING_MARK = "⚠" if sys.stdout.encoding.lower() == 'utf-8' else "!"
ERROR_MARK = "✗" if sys.stdout.encoding.lower() == 'utf-8' else "X"

# Check if we can use OCR as a fallback
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Assume script runs from project root
INPUT_DIR_NAME = "resumes"
OUTPUT_DIR_NAME = "markdown_resumes"

def clean_text(text):
    """Clean and normalize text to handle encoding issues."""
    if text is None:
        return ""

    # Replace common problematic characters
    text = text.replace('\x00', '')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    return text.strip()

def detect_encoding(file_path):
    """Detect the encoding of a file."""
    with open(file_path, 'rb') as file:
        raw_data = file.read(4096)  # Read a chunk to detect encoding
        result = chardet.detect(raw_data)
        return result['encoding'] or 'utf-8'  # Default to utf-8 if detection fails

def try_ocr_on_pdf(file_path):
    """Try to extract text from PDF using OCR if available."""
    if not OCR_AVAILABLE:
        print("OCR not available. Install Pillow, pytesseract, and Tesseract OCR for better results.")
        return "OCR extraction failed: Requirements not installed"

    try:
        print("  Attempting OCR extraction...")
        # Create a temporary directory for image files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to convert PDF to images using external tools
            try:
                # Try using pdftoppm (from poppler-utils)
                subprocess.run(
                    ['pdftoppm', '-png', file_path, os.path.join(temp_dir, 'page')],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except (subprocess.SubprocessError, FileNotFoundError):
                try:
                    # Fallback to convert (from ImageMagick)
                    subprocess.run(
                        ['convert', '-density', '300', file_path, os.path.join(temp_dir, 'page.png')],
                        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                except (subprocess.SubprocessError, FileNotFoundError):
                    return "OCR extraction failed: Required tools not installed (poppler-utils or ImageMagick)"

            # Process all images in the temp directory
            ocr_text = ""
            for img_file in sorted(os.listdir(temp_dir)):
                if img_file.endswith(('.png', '.jpg', '.jpeg')):
                    img_path = os.path.join(temp_dir, img_file)
                    img = Image.open(img_path)
                    page_text = pytesseract.image_to_string(img)
                    ocr_text += page_text + "\n\n"

            return clean_text(ocr_text) if ocr_text else "OCR extraction failed: No text detected"
    except Exception as e:
        return f"OCR extraction failed: {str(e)}"

def extract_text_with_pymupdf(file_path):
    """Extract text from PDF using PyMuPDF (better for text extraction)."""
    try:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text() + "\n\n"
        return clean_text(text)
    except Exception as e:
        print(f"  PyMuPDF extraction error: {e}")
        return None

def extract_text_with_tesseract(file_path):
    """Extract text from PDF using Tesseract OCR."""
    try:
        # Check if tesseract is installed
        try:
            if OCR_AVAILABLE:
                # Quick test if tesseract is installed
                version = pytesseract.get_tesseract_version()
                print(f"  Using Tesseract OCR version: {version}")
        except Exception as e:
            print(f"  Tesseract OCR is not properly installed: {e}")
            return None

        # Save each page as an image and perform OCR
        print("  Using OCR for text extraction...")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Use PyMuPDF to convert PDF pages to images
            doc = fitz.open(file_path)
            text = ""

            for page_num, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                img_path = os.path.join(temp_dir, f"page_{page_num+1}.png")
                pix.save(img_path)

                try:
                    # Use Tesseract OCR on the image
                    img = Image.open(img_path)
                    page_text = pytesseract.image_to_string(img, lang='eng')
                    text += page_text + "\n\n"
                    print(f"  ↳ OCR processed page {page_num+1}/{len(doc)}", end="\r")
                except Exception as e:
                    print(f"  ↳ OCR failed on page {page_num+1}: {e}")

            print(" " * 80, end="\r")  # Clear the progress line
            doc.close()

            if text.strip():
                return clean_text(text)
            return None
    except Exception as e:
        print(f"  OCR extraction failed: {e}")
        return None

def extract_text_from_pdf(file_path):
    """Extract text from PDF using PyMuPDF as primary method, OCR as fallback."""
    text = None
    errors = []

    # First, try PyMuPDF (primary method)
    text = extract_text_with_pymupdf(file_path)

    # If PyMuPDF failed or got minimal text, try OCR if available
    if not text or len(text.strip()) < 100:  # If empty or too short
        if OCR_AVAILABLE:
            print("  PyMuPDF extraction failed or minimal text extracted. Trying OCR...")
            ocr_text = extract_text_with_tesseract(file_path)
            if ocr_text and len(ocr_text.strip()) > len(text.strip() if text else ""):
                text = ocr_text

    # If both PyMuPDF and OCR failed, try PyPDF2 as last resort
    if not text or len(text.strip()) < 100:
        try:
            print("  Trying PyPDF2 as last resort...")
            text = ""
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n\n"
            text = clean_text(text)
        except Exception as e:
            errors.append(f"PyPDF2 extraction error: {str(e)}")

    # If all methods failed, return error info
    if not text or len(text.strip()) < 100:  # If empty or too short
        error_text = f"# Failed to extract text from {Path(file_path).name}\n\n"
        error_text += "## Errors encountered:\n\n"
        for err in errors:
            error_text += f"- {err}\n"

        if not OCR_AVAILABLE:
            error_text += "- OCR not available. Please install Pillow and pytesseract.\n"

        error_text += "\n## Recommendations:\n\n"
        error_text += "- Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki\n"
        error_text += "- Set the Tesseract path in the script\n"
        error_text += "- Try installing PyMuPDF (pip install PyMuPDF) for better PDF extraction\n"
        return error_text

    return text

def extract_text_from_docx(file_path):
    """Extract text from DOCX with improved formatting."""


    try:
        doc = docx.Document(file_path)

        # Extract content with better formatting
        markdown_content = ""

        # Process paragraphs with style preservation
        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            # Handle headings
            try:
                if para.style and para.style.name and para.style.name.startswith('Heading'):
                    heading_level = 1
                    if para.style.name[-1].isdigit():
                        heading_level = int(para.style.name[-1])
                    markdown_content += '#' * heading_level + ' ' + para.text.strip() + '\n\n'

                # Handle bullet points
                elif para.style and para.style.name and para.style.name.startswith('List'):
                    markdown_content += '* ' + para.text.strip() + '\n'

                # Handle normal paragraphs with emphasis
                else:
                    text = para.text.strip()

                    # Apply formatting for bold, italic, etc.
                    for run in para.runs:
                        if run.bold and run.text in text:
                            text = text.replace(run.text, f'**{run.text}**')
                        if run.italic and run.text in text:
                            text = text.replace(run.text, f'*{run.text}*')
                        if run.underline and run.text in text:
                            text = text.replace(run.text, f'_{run.text}_')

                    markdown_content += text + '\n\n'
            except Exception as style_error:
                # If style processing fails, just add the text
                markdown_content += para.text.strip() + '\n\n'

        # Process tables with markdown formatting
        for table in doc.tables:
            if len(table.rows) == 0:
                continue

            # Get maximum width for each column for better formatting
            col_count = len(table.columns)

            # Add header row
            if len(table.rows) > 0:
                markdown_content += '| '
                for cell in table.rows[0].cells:
                    cell_text = cell.text.strip().replace('|', '\\|')
                    markdown_content += cell_text + ' | '
                markdown_content += '\n'

                # Add separator row
                markdown_content += '| '
                for _ in range(col_count):
                    markdown_content += '--- | '
                markdown_content += '\n'

                # Add data rows
                for row_idx, row in enumerate(table.rows):
                    if row_idx == 0:  # Skip header row as we've already processed it
                        continue

                    markdown_content += '| '
                    for cell in row.cells:
                        cell_text = cell.text.strip().replace('|', '\\|')
                        markdown_content += cell_text + ' | '
                    markdown_content += '\n'

                markdown_content += '\n'

        return clean_text(markdown_content)
    except Exception as e:
        print(f"  DOCX extraction error: {e}")

        # Fallback to simpler extraction
        try:
            doc = docx.Document(file_path)
            text = '\n\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

            # Try to extract tables too
            for table in doc.tables:
                for row in table.rows:
                    text += '\n' + ' | '.join([cell.text.strip() for cell in row.cells]) + '\n'

            return clean_text(text)
        except Exception as inner_e:
            # Second fallback: try to read as plain text
            try:
                encoding = detect_encoding(file_path)
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
                    # Clean up the raw content
                    content = re.sub(r'[^\x00-\x7F]+', ' ', content)  # Remove non-ASCII
                    return clean_text(content)
            except:
                return f"# Failed to extract text from {Path(file_path).name}\n\n" \
                       f"## Errors:\n- {str(e)}\n- {str(inner_e)}\n\n" \
                       f"This file may be corrupted or in an unsupported format."

def save_as_markdown(text, output_path):
    """Save text as markdown with proper encoding."""
    try:
        with open(output_path, 'w', encoding='utf-8', errors='replace') as file:
            file.write(text)
        return True
    except Exception as e:
        print(f"  Error saving markdown file {output_path}: {e}")
        return False

def main():
    # Set Tesseract path if needed (for Windows)
    if OCR_AVAILABLE and os.name == 'nt':
        # Uncomment and adjust this line if Tesseract is not in PATH
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pass

    # Use project root directory to find the resumes folder
    # Assume the script is in 'src' and the project root is one level up
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_directory = os.path.join(project_root, INPUT_DIR_NAME) # INPUT_DIR_NAME is "resumes"
    output_directory = os.path.join(project_root, OUTPUT_DIR_NAME) # OUTPUT_DIR_NAME is "markdown_resumes"

    # Create output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)

    # Track processed files
    processed_count = 0
    error_count = 0
    error_files = []

    print(f"Looking for files in: {input_directory}")

    # Print OCR availability status
    if OCR_AVAILABLE:
        print("OCR support is available (used as fallback for PDF extraction)")
    else:
        print("WARNING: OCR support is NOT available. Install Pillow and pytesseract.")
        print("For best results with PDFs, install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")

    # Process all files in the input directory
    if not os.path.isdir(input_directory):
        print(f"Error: Input directory '{input_directory}' not found.")
        return

    files = [f for f in os.listdir(input_directory) if not os.path.isdir(os.path.join(input_directory, f))]
    total_files = len(files)

    for idx, file_name in enumerate(files):
        file_path = os.path.join(input_directory, file_name)

        # Skip directories
        if os.path.isdir(file_path):
            continue

        print(f"Processing: {file_name} ({idx+1}/{total_files})")
        start_time = time.time()

        # Create markdown filename with the same base name
        markdown_file_name = f"{Path(file_name).stem}.md"
        output_path = os.path.join(output_directory, markdown_file_name)

        # Flag to track if this file had an error
        had_error = False

        try:
            # Extract text based on file extension
            if file_name.lower().endswith('.pdf'):
                text = extract_text_from_pdf(file_path)
            elif file_name.lower().endswith(('.docx', '.doc')):
                text = extract_text_from_docx(file_path)
            else:
                print(f"  Skipping unsupported file: {file_name}")
                continue

            # Save as markdown
            if save_as_markdown(text, output_path):
                elapsed_time = time.time() - start_time
                file_size = os.path.getsize(output_path)

                # Check if successful based on content size and text quality
                if text and not text.startswith("# Failed") and file_size > 100: # Reduced threshold slightly
                    print(f"  {CHECK_MARK} Successfully converted {file_name} [{file_size/1024:.1f}KB] in {elapsed_time:.1f}s")
                    processed_count += 1
                else:
                    print(f"  {WARNING_MARK} Converted {file_name} but output may have issues (size: {file_size} bytes)")
                    error_count += 1
                    had_error = True
                    # Keep potentially problematic files for review instead of deleting immediately
                    # error_files.append(output_path)
            else:
                print(f"  {ERROR_MARK} Failed to save {markdown_file_name}")
                error_count += 1
                had_error = True
                # Keep potentially problematic files for review instead of deleting immediately
                # error_files.append(output_path)

        except Exception as e:
            print(f"  {ERROR_MARK} Error processing {file_name}: {e}")
            error_count += 1
            had_error = True
            # Keep potentially problematic files for review instead of deleting immediately
            # if os.path.exists(output_path):
            #     error_files.append(output_path)

    # Commented out automatic deletion of error files for review purposes
    # if error_files:
    #     print("\nCleaning up files with errors...")
    #     for error_file in error_files:
    #         if os.path.exists(error_file):
    #             try:
    #                 os.remove(error_file)
    #                 print(f"  Deleted: {os.path.basename(error_file)}")
    #             except Exception as e:
    #                 print(f"  Failed to delete {os.path.basename(error_file)}: {e}")

    print(f"\nSummary: Successfully processed {processed_count} files")
    print(f"Files with errors or potential issues: {error_count}")
    print(f"Markdown files saved to: {output_directory}")

if __name__ == "__main__":
    main()