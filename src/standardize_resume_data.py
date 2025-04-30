import csv
import os
import re
import pandas as pd
import numpy as np
from pathlib import Path

# Directory names
DATA_DIR = "data"
# Get the project root directory (one level up from script location)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Full paths using project root
DATA_PATH = os.path.join(PROJECT_ROOT, DATA_DIR)
INPUT_FILE = os.path.join(DATA_PATH, "resume_data.csv")
OUTPUT_FILE = os.path.join(DATA_PATH, "formatted_resume_data.csv")

def standardize_name(name):
    """Standardize name capitalization"""
    if pd.isna(name) or not name or name == "NA" or (isinstance(name, str) and name.upper() == "NA"):
        return "NA"
    
    # Convert to string if not already
    name = str(name)  # Convert to string in case it's a number
    
    # Handle special case of spaced letters with capitalization like "A M A R E S H" or "PA N D E Y"
    # First check if we have a pattern like "P A N D E Y" or "P a n d e y"
    parts = name.split()
    
    # Handle common cases where letters are separated by spaces
    if len(parts) > 2:
        # Check if most parts are single letters
        single_letters = sum(1 for part in parts if len(part) == 1)
        if single_letters > len(parts) / 2:
            # Join all parts without spaces (A M A R E S H -> AMARESH)
            name = ''.join(parts)
    
    # Special handling for names like "PA N D E Y" with some multi-letter parts and some single-letter parts
    # Look for patterns like P A N D E Y or Pa N D E Y
    elif re.search(r'[A-Za-z]{1,2}\s+[A-Za-z]\s+[A-Za-z]', name):
        # Fix patterns like "Pa N D E Y" by joining letters
        modified_parts = []
        
        # Find and join consecutive single letters
        i = 0
        while i < len(parts):
            current_part = parts[i]
            
            # Check if current part is followed by multiple single letter parts
            if i < len(parts) - 1 and len(parts[i+1]) == 1:
                j = i + 1
                while j < len(parts) and len(parts[j]) == 1:
                    current_part += parts[j]
                    j += 1
                i = j  # Skip processed parts
            else:
                i += 1
                
            modified_parts.append(current_part)
            
        name = ' '.join(modified_parts)
    
    # Special case for names like "K" or "A" or "K SAI KIRAN"
    # If first name is a single letter followed by uppercase word(s)
    parts = name.split()
    if len(parts) > 1 and len(parts[0]) == 1 and parts[1].isupper():
        name = parts[0] + ' ' + ' '.join(''.join(word.split()) for word in parts[1:])
    
    # Handle mixed capitalization by normalizing everything first to lowercase
    name = name.lower()
    
    # Title case names (capitalize first letter of each word)
    name = ' '.join(word.capitalize() for word in name.split())
    
    # Handle prefixes and suffixes properly
    name = name.replace(" Mc", " Mc")  # For names like McDonald
    name = name.replace(" Mac", " Mac")
    
    # Special case for names with specific prefixes
    prefixes = ["Van ", "De ", "La ", "Von ", "St ", "O'", "Mc", "Mac"]
    for prefix in prefixes:
        if prefix.lower() in name.lower():
            pattern = re.compile(re.escape(prefix.lower()), re.IGNORECASE)
            name = pattern.sub(prefix, name)
    
    # Keep abbreviations uppercase
    name = re.sub(r'\b[A-Z]{2,}\b', lambda m: m.group(0).upper(), name)
    
    return name

def standardize_phone(phone):
    """Standardize phone number format"""
    if pd.isna(phone) or not phone or phone == "NA" or (isinstance(phone, str) and not any(c.isdigit() for c in phone)):
        return "NA"
    
    # Convert to string and remove all non-numeric characters except + sign
    phone = str(phone)
    digits = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # If there are no digits, return NA
    if not digits:
        return "NA"
    
    # Handle Indian phone numbers (most common in the dataset)
    if digits.startswith('+91'):
        # Format: +91 98765-43210
        remaining = digits[3:]
        if len(remaining) == 10:
            return f"+91 {remaining[:5]}-{remaining[5:]}"
        else:
            return f"+91 {remaining}"
    elif digits.startswith('91') and len(digits) >= 12:
        # Handle 91 without + (common in dataset)
        remaining = digits[2:]
        if len(remaining) == 10:
            return f"+91 {remaining[:5]}-{remaining[5:]}"
        else:
            return f"+91 {remaining}"
    elif len(digits) == 10:  # Standard 10-digit number
        return f"{digits[:5]}-{digits[5:]}"
    elif digits.startswith('+'):
        # Other international format with +
        country_code_end = min(4, len(digits) - 6)  # Leave at least 6 digits after code
        country_code = digits[:country_code_end]
        remaining = digits[country_code_end:]
        
        if len(remaining) > 8:
            # Split longer numbers into chunks
            mid = len(remaining) // 2
            return f"{country_code} {remaining[:mid]}-{remaining[mid:]}"
        else:
            return f"{country_code} {remaining}"
    else:
        # Try to format based on length
        if len(digits) == 11:  # Possibly US/Canada with leading 1
            return f"+1 {digits[1:4]}-{digits[4:7]}-{digits[7:]}"
        elif len(digits) == 12:  # Possibly India without +
            return f"+{digits[:2]} {digits[2:7]}-{digits[7:]}"
        else:
            # If format is unclear, return cleaned digits
            if len(digits) > 7:
                # Split into two parts if longer
                mid = len(digits) // 2
                return f"{digits[:mid]}-{digits[mid:]}"
            else:
                return digits

def standardize_email(email):
    """Standardize email addresses"""
    if pd.isna(email) or not email or email == "NA" or not isinstance(email, str):
        return "NA"
    
    # Remove any surrounding quotes
    email = email.strip('"\'')
    
    # Convert to lowercase
    email = email.lower().strip()
    
    # Check if it's a valid email format
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "NA"
        
    return email

def standardize_address(address):
    """Standardize address format"""
    if pd.isna(address) or not address or address == "NA" or not isinstance(address, str):
        return "NA"
    
    # Remove excessive spaces and standardize commas
    address = re.sub(r'\s+', ' ', address).strip()
    address = re.sub(r'\s*,\s*', ', ', address)
    
    # Remove redundant NA in address
    if address.upper() == "NA":
        return "NA"
    
    # Capitalize first letter of each sentence
    return address[0].upper() + address[1:] if address else "NA"

def standardize_job_title(title):
    """Standardize job title format"""
    if pd.isna(title) or not title or title == "NA" or (isinstance(title, str) and title.upper() == "NA"):
        return "NA"
    
    # Convert to string if not already
    title = str(title)
    
    # Title case job titles
    title = ' '.join(word.capitalize() for word in title.split())
    
    # Don't capitalize certain words like "and", "of", "in" unless they're the first word
    words_to_lowercase = ['and', 'of', 'in', 'for', 'with', 'at', 'the', 'on', 'by', 'to', 'a', 'an']
    words = title.split()
    
    for i in range(1, len(words)):  # Skip the first word
        if words[i].lower() in words_to_lowercase and not words[i-1].endswith('.'):
            words[i] = words[i].lower()
    
    # Handle specific abbreviations properly
    title = ' '.join(words)
    for abbr in ['Hr', 'Ai', 'Ui', 'Ux', 'Api', 'Vp', 'Ceo', 'Cfo', 'Cto', 'Cmo', 'Seo', 'Crm']:
        title = re.sub(r'\b' + abbr + r'\b', abbr.upper(), title)
    
    return title

def standardize_skills(skills):
    """Standardize skills formatting"""
    if pd.isna(skills) or not skills or skills == "NA" or (isinstance(skills, str) and skills.upper() == "NA"):
        return "NA"
    
    # Convert to string if not already
    skills = str(skills)
    
    # Normalize separators: convert all separators to commas
    skills = re.sub(r'[•|;|\\|/|●|–|-]', ',', skills)
    
    # Replace multiple commas with a single comma
    skills = re.sub(r',\s*,', ',', skills)
    
    # Split, trim, and deduplicate skills
    skill_list = [s.strip() for s in skills.split(',') if s.strip()]
    skill_list = list(dict.fromkeys(skill_list))  # Remove duplicates while preserving order
    
    # Join the skills back with standard comma and space separator
    return ', '.join(skill_list)

def standardize_education(education):
    """Standardize education formatting"""
    if pd.isna(education) or not education or education == "NA" or (isinstance(education, str) and education.upper() == "NA"):
        return "NA"
    
    # Convert to string if not already
    education = str(education)
    
    # Clean up multiple spaces
    education = re.sub(r'\s+', ' ', education)
    
    # Standardize separator for multiple education items
    education = re.sub(r'\s*;\s*', '; ', education)
    
    return education.strip()

def standardize_experience(experience):
    """Standardize experience formatting"""
    if pd.isna(experience) or not experience or experience == "NA" or (isinstance(experience, str) and experience.upper() == "NA"):
        return "NA"
    
    # Convert to string if not already
    experience = str(experience)
    
    # Clean up multiple spaces
    experience = re.sub(r'\s+', ' ', experience)
    
    # Standardize separator for multiple experience items
    experience = re.sub(r'\s*;\s*', '; ', experience)
    
    return experience.strip()

def standardize_postal_code(postal_code):
    """Standardize postal codes"""
    if pd.isna(postal_code) or not postal_code or postal_code == "NA" or (isinstance(postal_code, str) and postal_code.upper() == "NA"):
        return "NA"
    
    # Convert to string and strip
    postal_code = str(postal_code).strip()
    
    # If it's just a number, return it as is
    if postal_code.isdigit():
        return postal_code
    
    # If it contains non-alphanumeric characters (except for space/dash), convert to NA
    if re.search(r'[^a-zA-Z0-9\s\-]', postal_code):
        return "NA"
    
    return postal_code

def standardize_score(score):
    """Standardize score values"""
    if pd.isna(score) or score == "NA" or not score:
        return "NA"
    
    # Convert to string
    score = str(score).strip()
    
    # If "NA", return as is
    if score.upper() == "NA":
        return "NA"
    
    # Try to convert to float for rounding
    try:
        score_value = float(score)
        return str(round(score_value, 1))
    except (ValueError, TypeError):
        # If conversion fails, return the original string
        return score

def validate_data(df):
    """Perform basic validation on the data and print statistics"""
    validation_issues = []
    
    # Check for email format
    invalid_emails = df[df['Email Address'] != "NA"].apply(
        lambda row: not re.match(r"[^@]+@[^@]+\.[^@]+", str(row['Email Address'])), axis=1
    ).sum()
    if invalid_emails > 0:
        validation_issues.append(f"Found {invalid_emails} potentially invalid email addresses")
    
    # Check for phone number format
    # This is a simple check - we're just making sure there are digits
    invalid_phones = df[df['Phone Number (primary)'] != "NA"].apply(
        lambda row: not any(c.isdigit() for c in str(row['Phone Number (primary)'])), axis=1
    ).sum()
    if invalid_phones > 0:
        validation_issues.append(f"Found {invalid_phones} potentially invalid phone numbers")
    
    # Check for empty full name but present first/last name
    name_inconsistencies = df[
        (df['Full Name'] == "NA") & 
        ((df['First Name'] != "NA") | (df['Last Name'] != "NA"))
    ].shape[0]
    if name_inconsistencies > 0:
        validation_issues.append(f"Found {name_inconsistencies} records with missing full name but present first/last name")
    
    # Check for location data consistency
    location_inconsistencies = df[
        (df['Country'] != "NA") & 
        (df['City'] == "NA") & 
        (df['Address'] != "NA")
    ].shape[0]
    if location_inconsistencies > 0:
        validation_issues.append(
            f"Found {location_inconsistencies} records with country and address but missing city"
        )
    
    return validation_issues

def main():
    input_file = INPUT_FILE
    output_file = OUTPUT_FILE

    if not Path(input_file).exists():
        print(f"Error: Input file {input_file} not found.")
        print(f"Please ensure you have run the 'extract_resume_data.py' script first.")
        return

    print(f"Reading {input_file}...")

    # Ensure data directory exists for output
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Read the CSV file into a pandas DataFrame
    # Use NA values handling to ensure consistent handling of missing data
    df = pd.read_csv(input_file, na_values=['NA', 'na', 'N/A', 'n/a', '', None])
    
    # Check for scoring columns
    score_columns = [
        "Skills Match Score", 
        "Education Match Score", 
        "Experience Match Score", 
        "Overall Score",
        "Weighted Score"
    ]
    has_scoring = all(col in df.columns for col in score_columns[:4])
    has_weighted_score = "Weighted Score" in df.columns
    
    if has_scoring:
        print("Resume scoring data detected. These columns will be preserved.")
    
    # Convert all NA values to string "NA" for consistent processing
    df = df.fillna("NA")
    
    # Store original NA counts for comparison
    original_na_counts = {col: (df[col] == "NA").sum() for col in df.columns}
    
    # Apply standardization to each column
    print("Standardizing data...")
    
    # Standardize name columns
    name_columns = ['First Name', 'Last Name', 'Full Name']
    for col in name_columns:
        df[col] = df[col].apply(standardize_name)
    
    # Create/Update full name from first and last names
    df['Full Name'] = df.apply(
        lambda row: f"{row['First Name']} {row['Last Name']}" 
        if row['First Name'] != "NA" and row['Last Name'] != "NA"
        else row['Full Name'],
        axis=1
    )
    
    # Fix cases where full name doesn't have a space between first and last name
    df['Full Name'] = df.apply(
        lambda row: f"{row['First Name']} {row['Last Name']}"
        if row['Full Name'] != "NA" and 
           row['First Name'] != "NA" and 
           row['Last Name'] != "NA" and
           not re.search(r'\s', row['Full Name'])
        else row['Full Name'],
        axis=1
    )
    
    # Standardize phone numbers
    phone_columns = ['Phone Number (primary)', 'Alternative Phone (mobile/secondary)']
    for col in phone_columns:
        df[col] = df[col].apply(standardize_phone)
    
    # Standardize email
    df['Email Address'] = df['Email Address'].apply(standardize_email)
    
    # Standardize location data
    location_columns = ['Address', 'City', 'State/Province', 'Country']
    for col in location_columns:
        df[col] = df[col].apply(standardize_address)
    
    # Standardize job title
    df['Current Job Title'] = df['Current Job Title'].apply(standardize_job_title)
    
    # Standardize skills
    df['Skills'] = df['Skills'].apply(standardize_skills)
    
    # Standardize education and experience
    df['Education'] = df['Education'].apply(standardize_education)
    df['Experience'] = df['Experience'].apply(standardize_experience)
    
    # Standardize Zip/Postal Code
    df['Zip/Postal Code'] = df['Zip/Postal Code'].apply(standardize_postal_code)
    
    # Standardize score columns if present
    if has_scoring:
        for col in score_columns[:4]:  # The first four score columns
            if col in df.columns:
                df[col] = df[col].apply(standardize_score)
    
    if has_weighted_score:
        df['Weighted Score'] = df['Weighted Score'].apply(standardize_score)
    
    # Add data cleaning statistics
    new_na_counts = {col: (df[col] == "NA").sum() for col in df.columns}
    
    print("\nStandardization Statistics:")
    for col in df.columns:
        if col == "Filename":
            continue
        filled_percent = 100 * (1 - new_na_counts[col] / len(df))
        diff = original_na_counts.get(col, 0) - new_na_counts[col]
        diff_str = f" ({diff:+d} change)" if diff != 0 else ""
        print(f"{col}: {filled_percent:.1f}% filled{diff_str}")
    
    # Validate the data
    print("\nValidating data...")
    validation_issues = validate_data(df)
    
    if validation_issues:
        print("Validation issues found:")
        for issue in validation_issues:
            print(f"- {issue}")
    else:
        print("No major validation issues found.")

    # Write the standardized data to the output file
    df.to_csv(output_file, index=False, quoting=csv.QUOTE_ALL)

    print(f"\nStandardized data written to {output_file}")

if __name__ == "__main__":
    main()