"""
Symbol Parser for K2Edit Agentic System
Handles symbol extraction and parsing from LSP responses
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiologger import Logger


class SymbolParser:
    """Handles symbol extraction and parsing from LSP responses"""
    
    def __init__(self, logger: Logger = None):
        self.logger = logger or Logger(name="k2edit-symbols")
    
    async def parse_lsp_symbols(self, lsp_symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse LSP symbols into our format"""
        symbols = []

        def parse_symbol(symbol: Dict[str, Any], parent: str = None):
            kind_map = {
                1: "file", 2: "module", 3: "namespace", 4: "package",
                5: "class", 6: "method", 7: "property", 8: "field",
                9: "constructor", 10: "enum", 11: "interface", 12: "function",
                13: "variable", 14: "constant", 15: "string", 16: "number",
                17: "boolean", 18: "array", 19: "object", 20: "key",
                21: "null", 22: "enum_member", 23: "struct", 24: "event",
                25: "operator", 26: "type_parameter"
            }

            try:
                # Handle different symbol formats
                if isinstance(symbol, str):
                    return

                name = symbol.get("name", "")
                kind = kind_map.get(symbol.get("kind", 0), "unknown")
                
                # Handle different location formats
                location = symbol.get("location", symbol)
                range_info = location.get("range", symbol)
                
                start_line = range_info.get("start", {}).get("line", 0) + 1
                end_line = range_info.get("end", {}).get("line", 0) + 1

                symbol_data = {
                    "name": name,
                    "kind": kind,
                    "type": kind,
                    "parent": parent,
                    "children": [],
                    "start_line": start_line,
                    "end_line": end_line
                }

                symbols.append(symbol_data)

                # Handle nested symbols
                children = symbol.get("children", [])
                for child in children:
                    parse_symbol(child, name)
                    
            except Exception as e:
                pass
                return []

        # Handle both list and dict formats
        try:
            if isinstance(lsp_symbols, list):
                for symbol in lsp_symbols:
                    parse_symbol(symbol)
            elif isinstance(lsp_symbols, dict):
                parse_symbol(lsp_symbols)
        except Exception as e:
            pass

        return symbols
    
    def build_hierarchical_outline(self, symbols: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build hierarchical outline from flat symbol list"""
        outline = []
        
        # Build hierarchy
        for symbol in symbols:
            if not symbol.get("parent"):
                # Top-level symbol
                outline.append(self._build_symbol_tree(symbol, symbols))
                
        return outline
    
    def _build_symbol_tree(self, symbol: Dict[str, Any], all_symbols: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build symbol tree with nested children"""
        tree = symbol.copy()
        tree["children"] = []
        
        # Find children (symbols with this symbol as parent)
        for child in all_symbols:
            if child.get("parent") == symbol["name"]:
                tree["children"].append(self._build_symbol_tree(child, all_symbols))
                
        return tree
    
    async def extract_dependencies(self, file_path: str, language: str) -> List[str]:
        """Extract dependencies from a file based on language"""
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return []
        
        try:
            if language == "python":
                return await self._get_python_imports(file_path_obj)
            elif language in ["javascript", "typescript"]:
                return await self._get_javascript_imports(file_path_obj)
            elif language == "nim":
                return await self._get_nim_imports(file_path_obj)
            else:
                return await self._get_generic_imports(file_path_obj)
        except Exception as e:
            await self.logger.warning(f"Failed to extract dependencies from {file_path}: {e}")
            return []
    
    async def _get_python_imports(self, file_path: Path) -> List[str]:
        """Get Python imports"""
        imports = []
        try:
            content = file_path.read_text()
            
            # Basic import patterns
            patterns = [
                r'^import\s+([\w.]+)',
                r'^from\s+([\w.]+)\s+import',
                r'^import\s+([\w.]+)\s+as'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse Python imports from {file_path}: {e}")
            
        return imports
    
    async def _get_javascript_imports(self, file_path: Path) -> List[str]:
        """Get JavaScript/TypeScript imports"""
        imports = []
        try:
            content = file_path.read_text()
            
            # Basic import patterns
            patterns = [
                r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
                r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                r'import\s+[\'"]([^\'"]+)[\'"]'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse JavaScript imports from {file_path}: {e}")
            
        return imports
    
    async def _get_nim_imports(self, file_path: Path) -> List[str]:
        """Get Nim imports"""
        imports = []
        try:
            content = file_path.read_text()
            
            # Basic import patterns for Nim
            patterns = [
                r'^import\s+([\w/]+)',
                r'^from\s+([\w/]+)\s+import',
                r'^include\s+([\w/]+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
                
        except Exception as e:
            await self.logger.warning(f"Failed to parse Nim imports from {file_path}: {e}")
            
        return imports
    
    async def _get_generic_imports(self, file_path: Path) -> List[str]:
        """Generic import extraction for unsupported languages"""
        return []
    
    async def get_document_outline(self, symbols: List[Dict[str, Any]], file_path: str, language: str) -> Dict[str, Any]:
        """Get structured outline for a document"""
        # Build hierarchical outline
        outline = self.build_hierarchical_outline(symbols)
        
        # Extract dependencies
        dependencies = await self.extract_dependencies(file_path, language)
        
        return {
            "file_path": str(Path(file_path).name),
            "language": language,
            "outline": outline,
            "symbol_count": len(symbols),
            "classes": [s for s in symbols if s.get("kind") == "class"],
            "functions": [s for s in symbols if s.get("kind") in ["function", "method"]],
            "variables": [s for s in symbols if s.get("kind") in ["variable", "constant", "property"]],
            "dependencies": dependencies
        }
    
    async def get_symbol_statistics(self, symbols_by_file: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Get statistics about symbols across files"""
        total_files = len(symbols_by_file)
        total_symbols = 0
        symbol_type_counts = {}
        
        for file_path, symbols in symbols_by_file.items():
            total_symbols += len(symbols)
            
            for symbol in symbols:
                symbol_type = symbol.get("kind", "unknown")
                symbol_type_counts[symbol_type] = symbol_type_counts.get(symbol_type, 0) + 1
        
        return {
            "total_files": total_files,
            "total_symbols": total_symbols,
            "symbol_type_breakdown": symbol_type_counts,
            "average_symbols_per_file": total_symbols / total_files if total_files > 0 else 0
        }