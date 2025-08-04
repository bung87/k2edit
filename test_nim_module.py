#!/usr/bin/env python3
"""Test script for the Nim highlight module."""

def test_nim_highlight_module():
    """Test the Nim highlight module functionality."""
    print("Testing Nim highlight module...")
    
    try:
        from nim_highlight import is_nim_available, get_nim_language, get_nim_highlight_query
        
        # Test availability
        print(f"tree-sitter-nim available: {is_nim_available()}")
        
        if is_nim_available():
            # Test language object
            nim_language = get_nim_language()
            print(f"Nim language object: {nim_language}")
            
            # Test highlight query
            query = get_nim_highlight_query()
            print(f"Highlight query length: {len(query)} characters")
            print("Query preview:")
            print(query[:200] + "..." if len(query) > 200 else query)
            
            print("✅ Nim highlight module test passed!")
        else:
            print("⚠️  tree-sitter-nim not available")
            
    except Exception as e:
        print(f"❌ Error testing Nim highlight module: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_nim_highlight_module() 