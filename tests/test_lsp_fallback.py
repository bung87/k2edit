#!/usr/bin/env python3
"""
Test script demonstrating LSP integration with fallback to regex-based parsing
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path

from agent.context_manager import AgenticContextManager
from agent.lsp_indexer import LSPIndexer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_lsp_with_fallback():
    """Test LSP integration with fallback parsing"""
    
    # Create a temporary test project
    with tempfile.TemporaryDirectory() as test_dir:
        test_path = Path(test_dir)
        
        # Create test Python files
        test_file = test_path / "test_module.py"
        test_file.write_text('''
class Calculator:
    """A simple calculator class"""
    
    def __init__(self):
        self.history = []
    
    def add(self, a: int, b: int) -> int:
        """Add two numbers"""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def multiply(self, x: float, y: float) -> float:
        """Multiply two numbers"""
        return x * y

class DataProcessor:
    """Process data with calculator"""
    
    def __init__(self, calculator: Calculator):
        self.calculator = calculator
    
    def process_numbers(self, numbers: list) -> list:
        """Process a list of numbers"""
        results = []
        for i in range(0, len(numbers) - 1, 2):
            if i + 1 < len(numbers):
                result = self.calculator.add(numbers[i], numbers[i + 1])
                results.append(result)
        return results

# Global function
def utility_function():
    """A utility function"""
    return "utility"

if __name__ == "__main__":
    calc = Calculator()
    processor = DataProcessor(calc)
''')
        
        print(f"Created test project at: {test_path}")
        
        # Test LSP indexer with fallback
        print("\n=== Testing LSP Indexer with Fallback ===")
        lsp_indexer = LSPIndexer(logger)
        await lsp_indexer.initialize(str(test_path))
        
        # Test document outline (should use fallback regex parsing)
        print("\n=== Testing Document Outline (Fallback) ===")
        outline = await lsp_indexer.get_document_outline(str(test_file))
        print(f"File: {outline['file_path']}")
        print(f"Language: {outline['language']}")
        print(f"Total symbols: {outline['symbol_count']}")
        print(f"Classes: {len(outline['classes'])}")
        print(f"Functions: {len(outline['functions'])}")
        
        print("\n=== Outline Structure ===")
        for item in outline['outline']:
            print(f"- {item['type']}: {item['name']} (lines {item['start_line']}-{item['end_line']})")
            if item.get('children'):
                for child in item['children']:
                    print(f"  - {child['type']}: {child['name']} (lines {child['start_line']}-{child['end_line']})")
        
        # Test AgentContext integration
        print("\n=== Testing AgentContext Integration ===")
        context_manager = AgenticContextManager(logger)
        await context_manager.initialize(str(test_path))
        
        # Update context with test file
        await context_manager.update_context(
            str(test_file),
            selected_code="def add(self, a: int, b: int) -> int:",
            cursor_position={"line": 8, "character": 8}
        )
        
        # Get enhanced context
        enhanced_context = await context_manager.get_enhanced_context("calculator methods")
        
        print(f"Current file: {enhanced_context.get('current_file')}")
        print(f"Language: {enhanced_context.get('language')}")
        print(f"Symbols count: {len(enhanced_context.get('symbols', []))}")
        
        if 'lsp_outline' in enhanced_context:
            print("\n=== LSP Outline in Context ===")
            for item in enhanced_context['lsp_outline']:
                print(f"- {item['type']}: {item['name']}")
        
        if 'lsp_metadata' in enhanced_context:
            print(f"\n=== LSP Metadata ===")
            metadata = enhanced_context['lsp_metadata']
            print(f"Total symbols: {metadata.get('total_symbols', 0)}")
            print(f"Classes: {metadata.get('classes', 0)}")
            print(f"Functions: {metadata.get('functions', 0)}")
        
        # Test line-specific context
        print("\n=== Testing Line-Specific Context ===")
        line_context = await lsp_indexer.get_enhanced_context_for_file(str(test_file), line=8)
        if line_context.get('line_context'):
            print("Symbols at line 8:")
            for symbol in line_context['line_context']:
                print(f"- {symbol['type']}: {symbol['name']}")
        
        # Test project-wide symbols
        print("\n=== Testing Project Symbols ===")
        project_symbols = await lsp_indexer.get_project_symbols()
        print(f"Total project symbols: {len(project_symbols)}")
        
        for symbol in project_symbols:
            print(f"- {symbol['file_path']}: {symbol['type']} {symbol['name']}")
        
        # Cleanup
        lsp_indexer.shutdown()
        
        print("\n=== Test Complete ===")
        print("LSP integration with fallback parsing completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_lsp_with_fallback())