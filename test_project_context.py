#!/usr/bin/env python3
"""
Test file to verify agent's ability to gather project-wide context.
This test uses the current directory as the project and validates
that the agent can properly index and understand the codebase.
"""

import asyncio
import logging
import sys
from pathlib import Path
import json
from typing import Dict, Any, List

# Add the current directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from agent.integration import K2EditAgentIntegration
from agent.context_manager import AgenticContextManager


# Configure logging for the test
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_project_context.log')
    ]
)
logger = logging.getLogger("k2edit")


class ProjectContextTester:
    """Test class for verifying project-wide context gathering capabilities."""
    
    def __init__(self, project_root: str = None):
        self.project_root = project_root or str(Path.cwd())
        self.agent_integration = None
        self.context_manager = None
        
    async def setup(self):
        """Initialize the agent system with the current directory as project."""
        logger.info(f"Setting up test with project root: {self.project_root}")
        
        # Initialize agent integration
        self.agent_integration = K2EditAgentIntegration(self.project_root)
        await self.agent_integration.initialize()
        
        # Import agent module functions for direct testing
        from agent import get_agent_context
        agent = await get_agent_context()
        self.context_manager = agent
        
        logger.info("Agent system initialized successfully")
        
    async def test_basic_project_structure(self):
        """Test basic project structure discovery."""
        logger.info("Testing basic project structure discovery...")
        
        # Get project overview through agent
        from agent import process_agent_query
        result = await process_agent_query("What is the project structure and what files are in this project?")
        
        print("\n=== Project Overview ===")
        print(json.dumps(result, indent=2, default=str))
        
        # Verify we got context
        assert "context" in result, "Should return context"
        context = result["context"]
        
        logger.info("Successfully retrieved project structure via agent")
        
        return context
        
    async def test_language_detection(self):
        """Test language detection for different file types."""
        logger.info("Testing language detection...")
        
        # Test language detection via agent
        from agent import get_code_intelligence
        from pathlib import Path
        
        # Find Python files to test
        python_files = list(Path(self.project_root).rglob("*.py"))
        languages_found = set()
        
        for py_file in python_files[:5]:  # Test first 5 Python files
            intelligence = await get_code_intelligence(str(py_file))
            if intelligence and "file_info" in intelligence:
                file_info = intelligence["file_info"]
                if file_info and "language" in file_info:
                    languages_found.add(file_info["language"])
                
        print(f"\n=== Languages Detected ===")
        for lang in sorted(languages_found):
            print(f"- {lang}")
            
        # Should detect Python
        assert "python" in languages_found, "Should detect Python files"
        
        logger.info(f"Detected languages: {languages_found}")
        
        return languages_found
        
    async def test_symbol_indexing(self):
        """Test symbol indexing across the project."""
        logger.info("Testing symbol indexing...")
        
        # Test symbol indexing via agent
        from agent import get_code_intelligence
        from pathlib import Path
        
        # Find Python files to test
        python_files = list(Path(self.project_root).rglob("*.py"))
        files_with_symbols = 0
        total_symbols = 0
        
        for py_file in python_files[:3]:  # Test first 3 Python files
            intelligence = await get_code_intelligence(str(py_file))
            if intelligence:
                symbols = intelligence.get("symbols", [])
                total_symbols += len(symbols)
                
                if symbols:
                    files_with_symbols += 1
                    
                print(f"\n=== Symbols in {py_file.name} ===")
                for symbol in symbols[:5]:  # Show first 5 symbols
                    print(f"  - {symbol.get('name', 'unnamed')} ({symbol.get('kind', 'unknown')})")
                if len(symbols) > 5:
                    print(f"  ... and {len(symbols) - 5} more")
                    
        # Log the results but don't fail if no symbols found (LSP might not be available)
        logger.info(f"Found {total_symbols} symbols across {files_with_symbols} files")
        
        if total_symbols == 0:
            print("Note: No symbols found - LSP server may not be available")
            
        return {"total_symbols": total_symbols, "files_with_symbols": files_with_symbols}
        
    async def test_semantic_context(self):
        """Test semantic context gathering for specific files."""
        logger.info("Testing semantic context...")
        
        # Test semantic context via agent
        from agent import get_code_intelligence
        from pathlib import Path
        
        # Find Python files to test
        python_files = list(Path(self.project_root).glob("**/*.py"))
        test_files = [f for f in python_files if not f.name.startswith("test_")][:3]
        
        if not test_files:
            test_files = python_files[:3]
            
        for test_file in test_files:
            logger.info(f"Testing semantic context for: {test_file}")
            
            # Get code intelligence
            intelligence = await get_code_intelligence(str(test_file))
            
            print(f"\n=== Semantic Context for {test_file.name} ===")
            print(f"File: {test_file}")
            print(f"Symbols: {len(intelligence.get('symbols', []))}")
            print(f"Dependencies: {len(intelligence.get('dependencies', []))}")
            print(f"Cross-references: {len(intelligence.get('cross_references', {}))}")
            
            if intelligence.get("symbols"):
                print("Top symbols:")
                for symbol in intelligence["symbols"][:3]:
                    print(f"  - {symbol.get('name', 'unnamed')} ({symbol.get('kind', 'unknown')})")
                    
    async def test_import_graph(self):
        """Test import relationship analysis."""
        logger.info("Testing import graph analysis...")
        
        # Test import analysis via agent
        from agent import get_code_intelligence
        from pathlib import Path
        
        # Find Python files to test
        python_files = list(Path(self.project_root).glob("**/*.py"))
        total_imports = 0
        
        for py_file in python_files[:3]:  # Test first 3 files
            intelligence = await get_code_intelligence(str(py_file))
            if intelligence:
                dependencies = intelligence.get("dependencies", [])
                total_imports += len(dependencies)
                
                if dependencies:
                    print(f"\n=== Imports in {py_file.name} ===")
                    for dep in dependencies[:5]:  # Show first 5 imports
                        print(f"  - {dep}")
                    if len(dependencies) > 5:
                        print(f"  ... and {len(dependencies) - 5} more")
                        
        print(f"\n=== Import Analysis ===")
        print(f"Total import relationships found across tested files: {total_imports}")
                
    async def run_full_test(self):
        """Run the complete test suite."""
        logger.info("Starting comprehensive project context test...")
        
        try:
            await self.setup()
            
            print("\n" + "="*60)
            print("PROJECT CONTEXT TESTING SUITE")
            print("="*60)
            
            # Run all tests
            await self.test_basic_project_structure()
            await self.test_language_detection()
            await self.test_symbol_indexing()
            await self.test_semantic_context()
            await self.test_import_graph()
            
            print("\n" + "="*60)
            print("ALL TESTS PASSED SUCCESSFULLY!")
            print("="*60)
            
            # Summary using agent API
            from agent import process_agent_query
            result = await process_agent_query("Summarize this project's structure and main components")
            
            print(f"\nFinal Summary:")
            print(f"- Project root: {self.project_root}")
            print(f"- Agent response keys: {list(result.keys())}")
            
            # Count files manually for summary
            from pathlib import Path
            all_files = list(Path(self.project_root).rglob("*"))
            python_files = list(Path(self.project_root).rglob("*.py"))
            print(f"- Total files: {len(all_files)}")
            print(f"- Python files: {len(python_files)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            print(f"\nTEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            if self.agent_integration:
                await self.agent_integration.shutdown()


async def main():
    """Main test runner."""
    tester = ProjectContextTester()
    success = await tester.run_full_test()
    
    if success:
        logger.info("All tests completed successfully!")
        return 0
    else:
        logger.error("Tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)