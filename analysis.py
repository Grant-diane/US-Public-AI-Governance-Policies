import json
import os
from collections import defaultdict
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import webbrowser

LIBRARY_PATH = os.path.join('AIPolicies_db', 'metadata', 'library.json')
DOCS_ROOT = os.path.join('AIPolicies_db', 'documents')

KEYWORDS = [
    'environment', 'climate', 'energy', 'sustainability',
    'carbon', 'emission', 'renewable', 'net zero', 'green'
]

SEARCH_FIELDS = ['title', 'abstract', 'note', 'extra_keywords']


def load_documents(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['documents']


def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
        return text
    except Exception as e:
        print(f"[WARN] Could not read PDF: {pdf_path} ({e})")
        return ''


def extract_text_from_html(html_path):
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        print(f"[WARN] Could not read HTML: {html_path} ({e})")
        return ''


def extract_fulltext_from_files(file_paths):
    # Only html and pdf is included because the dataset has only 
    #  these filetypes thus far
    fulltext = ''
    for rel_path in file_paths:
        abs_path = os.path.join('AIPolicies_db', rel_path.replace('\\', '/'))
        if abs_path.lower().endswith('.pdf'):
            fulltext += extract_text_from_pdf(abs_path) + '\n'
        elif abs_path.lower().endswith('.html'):
            fulltext += extract_text_from_html(abs_path) + '\n'
    return fulltext


def document_references_environment(doc):
    # Look through metadata
    for field in SEARCH_FIELDS:
        value = doc.get(field, '')
        if value:
            value_lower = value.lower()
            for kw in KEYWORDS:
                if kw in value_lower:
                    return True
    # Look through the file
    file_paths = doc.get('file_paths', [])
    if file_paths:
        fulltext = extract_fulltext_from_files(file_paths)
        fulltext_lower = fulltext.lower()
        for kw in KEYWORDS:
            if kw in fulltext_lower:
                return True
    return False


def group_stats_by_tag(documents):
    tag_env_counts = defaultdict(int)
    tag_total_counts = defaultdict(int)
    for doc in documents:
        tags = doc.get('tags', [])
        for tag in tags:
            tag_total_counts[tag] += 1
        if document_references_environment(doc):
            for tag in tags:
                tag_env_counts[tag] += 1
    return tag_env_counts, tag_total_counts


def filter_tags(tag_env_counts, tag_total_counts, filter_set):
    env = {tag: count for tag, count in tag_env_counts.items() if tag in filter_set}
    total = {tag: count for tag, count in tag_total_counts.items() if tag in filter_set}
    for tag in filter_set:
        env.setdefault(tag, 0)
        total.setdefault(tag, 0)
    return env, total


def main():
    documents = load_documents(LIBRARY_PATH)
    tag_env_counts, tag_total_counts = group_stats_by_tag(documents)
    print('Environmental/Climate/Energy Reference Statistics by Tag:')
    print('-' * 60)
    print(f'{"Tag":<15} {"With Env/Climate/Energy Ref":<25} {"Total Docs":<10}')
    print('-' * 60)
    for tag in sorted(tag_total_counts.keys()):
        env_count = tag_env_counts.get(tag, 0)
        total = tag_total_counts[tag]
        print(f'{tag:<15} {env_count:<25} {total:<10}')

    # Define tag groups
    state_city_tags = {'State', 'City'}
    region_tags = {'Midwest', 'Northeast', 'Pacific', 'South', 'West'}


if __name__ == '__main__':
    main()
