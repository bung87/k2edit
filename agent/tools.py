"""Local tool implementations for extended functionality."""

import os
import glob
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class ToolExecutor:
    """Executor for local tools that extend Kimi's capabilities."""
    
    def __init__(self, editor_widget=None):
        self.editor = editor_widget
        self.current_directory = Path.cwd()
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        try:
            if tool_name == "list_files":
                return await self.list_files(**arguments)
            elif tool_name == "search_code":
                return await self.search_code(**arguments)
            elif tool_name == "run_command":
                return await self.run_command(**arguments)
            elif tool_name == "analyze_code":
                return await self.analyze_code(**arguments)
            elif tool_name == "insert_code":
                return await self.insert_code(**arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    async def list_files(self, directory: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """List files in a directory with optional pattern filtering."""
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                return {"error": f"Directory not found: {directory}"}
            
            if not dir_path.is_dir():
                return {"error": f"Path is not a directory: {directory}"}
            
            files = []
            directories = []
            
            if pattern:
                # Use glob pattern
                for item in dir_path.glob(pattern):
                    if item.is_file():
                        files.append({
                            "name": item.name,
                            "path": str(item),
                            "size": item.stat().st_size,
                            "modified": item.stat().st_mtime
                        })
                    elif item.is_dir():
                        directories.append({
                            "name": item.name,
                            "path": str(item)
                        })
            else:
                # List all items
                for item in dir_path.iterdir():
                    if item.is_file():
                        files.append({
                            "name": item.name,
                            "path": str(item),
                            "size": item.stat().st_size,
                            "modified": item.stat().st_mtime
                        })
                    elif item.is_dir():
                        directories.append({
                            "name": item.name,
                            "path": str(item)
                        })
            
            return {
                "success": True,
                "directory": str(dir_path),
                "files": sorted(files, key=lambda x: x["name"]),
                "directories": sorted(directories, key=lambda x: x["name"]),
                "total_files": len(files),
                "total_directories": len(directories)
            }
        
        except Exception as e:
            return {"error": f"Failed to list files: {str(e)}"}
    
    async def search_code(self, pattern: str, directory: str = ".", file_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Search for code patterns in files."""
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                return {"error": f"Directory not found: {directory}"}
            
            matches = []
            
            # Find files matching the file pattern
            for file_path in dir_path.rglob(file_pattern):
                if not file_path.is_file():
                    continue
                
                # Skip binary files and common non-text files
                if file_path.suffix in ['.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe']:
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    for line_num, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            matches.append({
                                "file": str(file_path),
                                "line_number": line_num,
                                "line_content": line.strip(),
                                "match": pattern
                            })
                
                except (UnicodeDecodeError, PermissionError):
                    # Skip files that can't be read
                    continue
            
            return {
                "success": True,
                "pattern": pattern,
                "matches": matches,
                "total_matches": len(matches),
                "files_searched": len([f for f in dir_path.rglob(file_pattern) if f.is_file()])
            }
        
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}
    
    async def run_command(self, command: str, working_directory: str = ".") -> Dict[str, Any]:
        """Execute a shell command safely."""
        try:
            # Security check - block dangerous commands
            dangerous_commands = ['rm -rf', 'sudo', 'chmod 777', 'dd if=', 'mkfs', 'fdisk']
            if any(dangerous in command.lower() for dangerous in dangerous_commands):
                return {"error": "Command blocked for security reasons"}
            
            work_dir = Path(working_directory)
            if not work_dir.exists():
                return {"error": f"Working directory not found: {working_directory}"}
            
            # Execute command with timeout
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            return {
                "success": True,
                "command": command,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "working_directory": str(work_dir)
            }
        
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"error": f"Command execution failed: {str(e)}"}
    
    async def analyze_code(self, analysis_type: str, scope: str = "selection") -> Dict[str, Any]:
        """Analyze code structure and patterns."""
        try:
            if not self.editor:
                return {"error": "No editor available for analysis"}
            
            # Get code to analyze based on scope
            if scope == "selection":
                code = self.editor.get_selected_text()
                if not code.strip():
                    code = self.editor.text
            elif scope == "file":
                code = self.editor.text
            else:  # project scope
                return {"error": "Project scope analysis not implemented yet"}
            
            if not code.strip():
                return {"error": "No code to analyze"}
            
            # Perform analysis based on type
            if analysis_type == "structure":
                return self._analyze_structure(code)
            elif analysis_type == "dependencies":
                return self._analyze_dependencies(code)
            elif analysis_type == "complexity":
                return self._analyze_complexity(code)
            elif analysis_type == "style":
                return self._analyze_style(code)
            elif analysis_type == "security":
                return self._analyze_security(code)
            else:
                return {"error": f"Unknown analysis type: {analysis_type}"}
        
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    async def insert_code(self, line_number: int, code: str) -> Dict[str, Any]:
        """Insert code at a specific line in the editor."""
        try:
            if not self.editor:
                return {"error": "No editor available"}
            
            lines = self.editor.text.splitlines()
            
            # Insert at the specified line (1-based indexing)
            insert_index = max(0, min(line_number - 1, len(lines)))
            lines.insert(insert_index, code)
            
            self.editor.text = '\n'.join(lines)
            self.editor.is_modified = True
            
            return {
                "success": True,
                "message": f"Code inserted at line {line_number}",
                "line_number": line_number,
                "inserted_code": code
            }
        
        except Exception as e:
            return {"error": f"Code insertion failed: {str(e)}"}
    
    def _analyze_structure(self, code: str) -> Dict[str, Any]:
        """Analyze code structure (functions, classes, etc.)."""
        lines = code.splitlines()
        
        functions = []
        classes = []
        imports = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            if stripped.startswith('def '):
                func_name = stripped.split('(')[0].replace('def ', '')
                functions.append({"name": func_name, "line": i})
            
            elif stripped.startswith('class '):
                class_name = stripped.split('(')[0].split(':')[0].replace('class ', '')
                classes.append({"name": class_name, "line": i})
            
            elif stripped.startswith(('import ', 'from ')):
                imports.append({"statement": stripped, "line": i})
        
        return {
            "success": True,
            "analysis_type": "structure",
            "total_lines": len(lines),
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "summary": {
                "function_count": len(functions),
                "class_count": len(classes),
                "import_count": len(imports)
            }
        }
    
    def _analyze_dependencies(self, code: str) -> Dict[str, Any]:
        """Analyze code dependencies."""
        import_pattern = r'^\s*(?:from\s+([\w.]+)\s+)?import\s+([\w.,\s*]+)'
        
        dependencies = set()
        imports = []
        
        for line in code.splitlines():
            match = re.match(import_pattern, line)
            if match:
                module = match.group(1) or match.group(2).split(',')[0].strip()
                dependencies.add(module.split('.')[0])  # Get root module
                imports.append(line.strip())
        
        return {
            "success": True,
            "analysis_type": "dependencies",
            "dependencies": sorted(list(dependencies)),
            "import_statements": imports,
            "dependency_count": len(dependencies)
        }
    
    def _analyze_complexity(self, code: str) -> Dict[str, Any]:
        """Analyze code complexity (basic metrics)."""
        lines = code.splitlines()
        
        # Count various complexity indicators
        complexity_indicators = {
            "if_statements": len([l for l in lines if re.match(r'^\s*if\s+', l)]),
            "for_loops": len([l for l in lines if re.match(r'^\s*for\s+', l)]),
            "while_loops": len([l for l in lines if re.match(r'^\s*while\s+', l)]),
            "try_blocks": len([l for l in lines if re.match(r'^\s*try:', l)]),
            "nested_levels": max([len(l) - len(l.lstrip()) for l in lines if l.strip()]) // 4
        }
        
        # Simple complexity score
        complexity_score = sum(complexity_indicators.values())
        
        return {
            "success": True,
            "analysis_type": "complexity",
            "metrics": complexity_indicators,
            "complexity_score": complexity_score,
            "complexity_level": "low" if complexity_score < 10 else "medium" if complexity_score < 25 else "high"
        }
    
    def _analyze_style(self, code: str) -> Dict[str, Any]:
        """Analyze code style issues."""
        lines = code.splitlines()
        issues = []
        
        for i, line in enumerate(lines, 1):
            # Check for common style issues
            if len(line) > 100:
                issues.append({"line": i, "issue": "Line too long (>100 chars)", "severity": "warning"})
            
            if line.endswith(' '):
                issues.append({"line": i, "issue": "Trailing whitespace", "severity": "info"})
            
            if '\t' in line:
                issues.append({"line": i, "issue": "Tab character found (use spaces)", "severity": "warning"})
        
        return {
            "success": True,
            "analysis_type": "style",
            "issues": issues,
            "issue_count": len(issues),
            "style_score": max(0, 100 - len(issues) * 2)  # Simple scoring
        }
    
    def _analyze_security(self, code: str) -> Dict[str, Any]:
        """Analyze potential security issues."""
        security_patterns = {
            "eval_usage": r'\beval\s*\(',
            "exec_usage": r'\bexec\s*\(',
            "shell_injection": r'os\.system\s*\(|subprocess\.[^\s]*\s*\([^)]*shell\s*=\s*True',
            "hardcoded_secrets": r'(?i)(password|secret|key|token)\s*=\s*["\'][^"\'
]{8,}',
            "sql_injection": r'["\']\s*\+\s*\w+\s*\+\s*["\']|%s.*%\s*\(',
        }
        
        issues = []
        
        for pattern_name, pattern in security_patterns.items():
            for i, line in enumerate(code.splitlines(), 1):
                if re.search(pattern, line):
                    issues.append({
                        "line": i,
                        "issue": pattern_name.replace('_', ' ').title(),
                        "severity": "high" if pattern_name in ['eval_usage', 'exec_usage'] else "medium",
                        "line_content": line.strip()
                    })
        
        return {
            "success": True,
            "analysis_type": "security",
            "issues": issues,
            "issue_count": len(issues),
            "security_score": max(0, 100 - len(issues) * 10)  # Harsh penalty for security issues
        }