#!/usr/bin/env python3

# Debug the syntax highlighting issue
import sys
sys.path.insert(0, '/Users/bung/py_works/k2edit')

# Import the patch first
import tree_sitter_patch

from pathlib import Path

print("Testing language detection...")

# Test file extension mapping
path = Path('/Users/bung/py_works/k2edit/custom_syntax_editor.py')
extension = path.suffix.lower()
print(f"File: {path}")
print(f"Extension: {extension}")

# Test language mapping
language_map = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.html': 'html',
    '.css': 'css',
    '.json': 'json',
    '.xml': 'xml',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.md': 'markdown',
    '.nim': 'nim',
    '.c': 'c',
    '.cpp': 'cpp',
    '.h': 'c',
    '.hpp': 'cpp',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.php': 'php',
    '.rb': 'ruby',
    '.sh': 'bash',
    '.sql': 'sql',
}

language = language_map.get(extension)
print(f"Mapped language: {language}")

# Test tree_sitter_languages
if language and language != "text":
    try:
        import tree_sitter_languages
        print(f"✓ tree_sitter_languages imported")
        
        # Verify the language is available
        ts_language = tree_sitter_languages.get_language(language)
        print(f"✓ Language object obtained: {type(ts_language)}")
        print(f"✓ Language object: {ts_language}")
        
        # Test creating a SyntaxAwareDocument directly
        from textual.document._syntax_aware_document import SyntaxAwareDocument
        
        print("\nTesting SyntaxAwareDocument creation...")
        try:
            doc = SyntaxAwareDocument("print('hello world')\n", language=ts_language)
            print(f"✓ SyntaxAwareDocument created successfully")
            print(f"✓ Document language: {doc.language}")
        except Exception as e:
            print(f"✗ SyntaxAwareDocument creation failed: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError as e:
        print(f"✗ tree_sitter_languages import failed: {e}")
    except Exception as e:
        print(f"✗ Language setup failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"✗ No language mapping found for extension: {extension}")

print("\nDebug completed.")