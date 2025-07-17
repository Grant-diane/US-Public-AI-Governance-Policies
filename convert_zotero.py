"""
AI Written Code 
Convert Zotero BibTeX export + files folder to GitHub
"""

import json
import os
import shutil
import re
from pathlib import Path
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
import argparse
from datetime import datetime

def clean_filename(text):
    """Clean text for use as filename"""
    if not text:
        return "untitled"
    # Remove/replace problematic characters
    text = re.sub(r'[<>:"/\\|?*]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'[^\w\s-]', '', text)  # Remove special chars except dash
    return text[:80]  # Reasonable length limit

def parse_zotero_file_field(file_field):
    """Parse Zotero's file field format"""
    if not file_field:
        return []
    
    # Zotero file field format: "filename:path:mimetype"
    # Multiple files separated by semicolons
    files = []
    parts = file_field.split(';')
    
    for part in parts:
        if ':' in part:
            components = part.split(':')
            if len(components) >= 2:
                filename = components[0].strip()
                path = components[1].strip()
                if filename and path:
                    files.append({'filename': filename, 'path': path})
    
    return files

def find_pdf_in_files_folder(entry, files_dir):
    """Find PDF files for a BibTeX entry in the files folder"""
    if not files_dir or not os.path.exists(files_dir):
        return []
    
    files_path = Path(files_dir)
    found_pdfs = []
    
    # Method 1: Use file field if available
    if 'file' in entry:
        zotero_files = parse_zotero_file_field(entry['file'])
        for file_info in zotero_files:
            if file_info['filename'].lower().endswith('.pdf'):
                # Try to find the file in the files folder
                pdf_path = files_path / file_info['path']
                if pdf_path.exists():
                    found_pdfs.append(pdf_path)
                else:
                    # Try searching by filename in all subdirectories
                    for pdf_file in files_path.glob(f"**/{file_info['filename']}"):
                        found_pdfs.append(pdf_file)
    
    # Method 2: Search by entry ID or title if no file field
    if not found_pdfs:
        entry_id = entry.get('ID', '')
        title = entry.get('title', '')
        
        # Search all PDF files in the folder
        for pdf_file in files_path.glob('**/*.pdf'):
            filename_lower = pdf_file.name.lower()
            
            # Check if filename contains entry ID
            if entry_id and entry_id.lower() in filename_lower:
                found_pdfs.append(pdf_file)
                continue
            
            # Check if filename contains title words
            if title:
                title_words = [word.lower() for word in title.split() if len(word) > 3]
                if any(word in filename_lower for word in title_words[:3]):
                    found_pdfs.append(pdf_file)
    
    return found_pdfs

def extract_tags_from_entry(entry):
    """Extract tags from various BibTeX fields"""
    tags = set()
    
    # Common fields that contain tags
    tag_fields = ['keywords', 'mendeley-tags', 'tags', 'annote']
    
    for field in tag_fields:
        if field in entry:
            tag_text = entry[field]
            # Split by common delimiters
            for delimiter in [';', ',', '\n', '|']:
                if delimiter in tag_text:
                    field_tags = [tag.strip() for tag in tag_text.split(delimiter)]
                    tags.update(tag for tag in field_tags if tag)
                    break
            else:
                # No delimiter found, treat as single tag
                if tag_text.strip():
                    tags.add(tag_text.strip())
    
    return sorted(list(tags))

def categorize_entry(entry):
    """Determine category based on entry type"""
    entry_type = entry.get('ENTRYTYPE', '').lower()
    
    categories = {
        'article': 'journal_articles',
        'inproceedings': 'conference_papers',
        'proceedings': 'conference_papers',
        'book': 'books',
        'incollection': 'book_chapters',
        'inbook': 'book_chapters',
        'techreport': 'reports',
        'report': 'reports',
        'phdthesis': 'theses',
        'mastersthesis': 'theses',
        'thesis': 'theses',
        'patent': 'patents',
        'misc': 'miscellaneous',
        'unpublished': 'preprints',
        'online': 'web_resources',
        'webpage': 'web_resources',
        'software': 'software',
        'dataset': 'datasets'
    }
    
    return categories.get(entry_type, 'uncategorized')

def organize_pdf_files(pdf_files, entry, output_dir):
    """Copy PDF files to organized structure"""
    if not pdf_files:
        return []
    
    # Create directory structure
    year = entry.get('year', 'unknown')
    category = categorize_entry(entry)
    
    target_dir = Path(output_dir) / 'documents' / category / year
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate base filename
    first_author = ""
    if 'author' in entry:
        author_text = entry['author']
        # Extract first author's last name
        if ' and ' in author_text:
            first_author = author_text.split(' and ')[0]
        else:
            first_author = author_text.split(',')[0]
        
        # Get last name
        if ',' in first_author:
            first_author = first_author.split(',')[0].strip()
        else:
            first_author = first_author.split()[-1]
        
        first_author = clean_filename(first_author)
    
    title = clean_filename(entry.get('title', 'untitled'))
    base_filename = f"{first_author}_{year}_{title}"
    
    organized_files = []
    
    for i, pdf_file in enumerate(pdf_files):
        # Handle multiple PDFs
        if len(pdf_files) > 1:
            filename = f"{base_filename}_{i+1}.pdf"
        else:
            filename = f"{base_filename}.pdf"
        
        target_path = target_dir / filename
        
        # Copy file
        shutil.copy2(pdf_file, target_path)
        
        # Store relative path
        relative_path = str(target_path.relative_to(output_dir))
        organized_files.append(relative_path)
    
    return organized_files

def process_bibtex_export(export_dir, output_dir):
    """Main processing function"""
    export_path = Path(export_dir)
    output_path = Path(output_dir)
    
    # Find BibTeX file
    bib_files = list(export_path.glob('*.bib'))
    if not bib_files:
        raise FileNotFoundError("No .bib file found in export directory")
    
    bib_file = bib_files[0]
    files_dir = export_path / 'files'
    
    print(f"Processing BibTeX file: {bib_file}")
    print(f"Files directory: {files_dir}")
    print(f"Files directory exists: {files_dir.exists()}")
    
    # Parse BibTeX
    parser = BibTexParser()
    parser.customization = convert_to_unicode
    
    with open(bib_file, 'r', encoding='utf-8') as f:
        bib_database = bibtexparser.load(f, parser=parser)
    
    print(f"Found {len(bib_database.entries)} entries in BibTeX file")
    
    # Create output structure
    output_path.mkdir(exist_ok=True)
    (output_path / 'metadata').mkdir(exist_ok=True)
    (output_path / 'documents').mkdir(exist_ok=True)
    
    # Initialize database
    database = {
        "info": {
            "title": "Research Library",
            "description": "Converted from Zotero BibTeX export",
            "total_documents": len(bib_database.entries),
            "created": datetime.now().strftime("%Y-%m-%d"),
            "source": f"Zotero BibTeX Export ({bib_file.name})"
        },
        "documents": []
    }
    
    # Track statistics
    categories = {}
    all_tags = set()
    years = set()
    pdf_count = 0
    
    print(f"\nProcessing entries...")
    
    for i, entry in enumerate(bib_database.entries):
        title = entry.get('title', 'Untitled')
        print(f"  {i+1:3d}/{len(bib_database.entries)}: {title[:60]}...")
        
        # Extract tags
        tags = extract_tags_from_entry(entry)
        all_tags.update(tags)
        
        # Find PDF files
        pdf_files = find_pdf_in_files_folder(entry, files_dir)
        organized_files = organize_pdf_files(pdf_files, entry, output_path)
        
        if organized_files:
            pdf_count += 1
        
        # Extract year
        year = entry.get('year', '')
        if year:
            years.add(year)
        
        # Categorize
        category = categorize_entry(entry)
        categories[category] = categories.get(category, 0) + 1
        
        # Create document record
        doc = {
            "id": entry.get('ID', f"doc_{i}"),
            "title": title,
            "authors": entry.get('author', '').replace(' and ', ', '),
            "year": year,
            "journal": entry.get('journal', ''),
            "booktitle": entry.get('booktitle', ''),
            "publisher": entry.get('publisher', ''),
            "volume": entry.get('volume', ''),
            "number": entry.get('number', ''),
            "pages": entry.get('pages', ''),
            "doi": entry.get('doi', ''),
            "url": entry.get('url', ''),
            "isbn": entry.get('isbn', ''),
            "issn": entry.get('issn', ''),
            "abstract": entry.get('abstract', ''),
            "note": entry.get('note', ''),
            "tags": tags,
            "category": category,
            "entry_type": entry.get('ENTRYTYPE', ''),
            "file_paths": organized_files,
            "has_pdf": len(organized_files) > 0,
            "pdf_count": len(organized_files)
        }
        
        # Add any additional fields
        for key, value in entry.items():
            if key not in ['ID', 'ENTRYTYPE', 'title', 'author', 'year', 'journal', 
                          'booktitle', 'publisher', 'volume', 'number', 'pages', 
                          'doi', 'url', 'isbn', 'issn', 'abstract', 'note', 'file'] and value:
                doc[f"extra_{key}"] = value
        
        database["documents"].append(doc)
    
    # Update statistics
    database["info"]["categories"] = categories
    database["info"]["total_tags"] = len(all_tags)
    database["info"]["years"] = sorted(list(years))
    database["info"]["with_pdfs"] = pdf_count
    
    # Save files
    save_database_files(output_path, database, all_tags, categories)
    
    print(f"\n" + "="*60)
    print(f"Conversion complete!")
    print(f"Output directory: {output_path}")
    print(f"Total documents: {len(database['documents'])}")
    print(f"Documents with PDFs: {pdf_count}")
    print(f"Categories: {len(categories)}")
    print(f"Unique tags: {len(all_tags)}")
    print(f"Year range: {min(years) if years else 'N/A'} - {max(years) if years else 'N/A'}")
    print(f"\nCategory breakdown:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat.replace('_', ' ').title()}: {count}")

def save_database_files(output_path, database, all_tags, categories):
    """Save all database files"""
    
    # Main database
    with open(output_path / 'metadata' / 'library.json', 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    # Tags index
    with open(output_path / 'metadata' / 'tags.json', 'w', encoding='utf-8') as f:
        json.dump(sorted(list(all_tags)), f, indent=2, ensure_ascii=False)
    
    # Categories index
    with open(output_path / 'metadata' / 'categories.json', 'w', encoding='utf-8') as f:
        json.dump(categories, f, indent=2, ensure_ascii=False)
    
    # Create README
    create_readme(output_path, database)

def create_readme(output_path, database):
    """Create comprehensive README.md file"""
    readme_content = f"""# Research Library Database

Converted from Zotero BibTeX export on {database['info']['created']}

## 📊 Statistics
- **Total Documents**: {database['info']['total_documents']}
- **Documents with PDFs**: {database['info']['with_pdfs']}
- **Categories**: {len(database['info']['categories'])}
- **Unique Tags**: {database['info']['total_tags']}
- **Year Range**: {database['info']['years'][0] if database['info']['years'] else 'N/A'} - {database['info']['years'][-1] if database['info']['years'] else 'N/A'}

## 📚 Categories
"""
    
    for category, count in sorted(database['info']['categories'].items()):
        percentage = (count / database['info']['total_documents']) * 100
        readme_content += f"- **{category.replace('_', ' ').title()}**: {count} documents ({percentage:.1f}%)\n"
    
    readme_content += f"
---
*Generated from Zotero BibTeX export • Last updated: {database['info']['created']}*
"""
    
    with open(output_path / 'README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)

def main():
    parser = argparse.ArgumentParser(
        description='Convert Zotero BibTeX export + files folder to GitHub database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python convert_zotero.py /path/to/zotero-export /path/to/output
  
Where zotero-export contains:
  - My Library.bib (or similar .bib file)
  - files/ (folder with PDFs)
"""
    )
    
    parser.add_argument('export_dir', help='Path to Zotero export directory (contains .bib file and files/ folder)')
    parser.add_argument('output_dir', help='Path to output directory for GitHub database')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.export_dir):
        print(f"Error: Export directory '{args.export_dir}' does not exist")
        return 1
    
    try:
        process_bibtex_export(args.export_dir, args.output_dir)
        print(f"\n✅ Success! Your GitHub database is ready in: {args.output_dir}")
        print(f"📁 Next steps:")
        print(f"   1. cd {args.output_dir}")
        print(f"   2. git init && git add . && git commit -m 'Initial commit'")
        print(f"   3. Create GitHub repository and push")
        print(f"   4. Enable GitHub Pages for web interface")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
