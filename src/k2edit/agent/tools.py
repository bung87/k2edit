"""Local tool implementations for extended functionality."""

import re
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import aiofiles

class ToolExecutor:
    """Executor for local tools that extend Kimi's capabilities."""
    
    def __init__(self, logger, editor_widget=None, agent_integration=None):
        self.editor = editor_widget
        self.current_directory = Path.cwd()
        self.logger = logger
        self.agent_integration = agent_integration

    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
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
        elif tool_name == "replace_code":
            return await self.replace_code(**arguments)
        elif tool_name == "read_file":
            return await self.read_file(**arguments)
        elif tool_name == "write_file":
            return await self.write_file(**arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
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
        
        except (PermissionError, OSError) as e:
            error_type = type(e).__name__
            error_msg = f"{error_type} accessing directory {directory}: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
    async def search_code(self, pattern: str, directory: str = ".", file_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Search for code patterns in files."""
        try:
            dir_path = Path(directory)
            if not dir_path.exists():
                return {"error": f"Directory not found: {directory}"}
            
            matches = []
            
            # Determine file search pattern
            search_pattern = f"**/{pattern}" if pattern else "**/*"
            
            # Find files matching the file pattern
            for file_path in dir_path.rglob(search_pattern):
                if not file_path.is_file():
                    continue
                
                # Skip binary files and common non-text files
                if file_path.suffix in ['.pyc', '.pyo', '.so', '.dylib', '.dll', '.exe']:
                    continue
                
                try:
                    import aiofiles
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        lines = content.splitlines()
                    
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
                "files_searched": len([f for f in dir_path.rglob("**/*") if f.is_file()])
            }
        
        except PermissionError as e:
            error_msg = f"Permission denied searching in {directory}: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}
        except re.error as e:
            error_msg = f"Invalid regex pattern '{pattern}': {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
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
            
            # Execute command with timeout using async subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=30.0
                )
                result_stdout = stdout.decode('utf-8') if stdout else ''
                result_stderr = stderr.decode('utf-8') if stderr else ''
                return_code = process.returncode
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await self.logger.error("Command timed out after 30 seconds")
                return {"error": "Command timed out after 30 seconds"}
            
            return {
                "success": True,
                "command": command,
                "return_code": return_code,
                "stdout": result_stdout,
                "stderr": result_stderr,
                "working_directory": str(work_dir)
            }
        
        except subprocess.TimeoutExpired:
            await self.logger.error("Command timed out after 30 seconds")
            return {"error": "Command timed out after 30 seconds"}

    
    async def analyze_code(self, analysis_type: str, scope: str = "selection") -> Dict[str, Any]:
        """Analyze code structure, dependencies, or patterns using LSP when available."""
        if scope == "selection" and self.editor:
            content = self.editor.get_selected_text() or self.editor.text
            file_path = str(getattr(self.editor, 'current_file', '<current_file>'))
        elif scope == "file" and self.editor:
            content = self.editor.text
            file_path = str(getattr(self.editor, 'current_file', '<current_file>'))
        else:
            return {"error": "No content available for analysis"}
        
        if not content.strip():
            return {"error": "No code to analyze"}
        
        # Use LSP-based analysis when available
        lsp_result = await self._get_lsp_analysis(analysis_type, file_path, content)
        if lsp_result:
            return lsp_result
        
        # Return error if LSP is not available
        return {"error": f"LSP-based analysis not available for {analysis_type}. Please ensure LSP server is running."}
                


    async def _get_lsp_analysis(self, analysis_type: str, file_path: str, content: str) -> Optional[Dict[str, Any]]:
        """Get LSP-based code analysis when available."""
        if not self.agent_integration or not self.agent_integration.lsp_client:
            return None
        
        try:
            # Get the agent context for LSP access
            from . import get_agent_context
            agent = await get_agent_context()
            if not agent or not agent.lsp_indexer:
                return None
            
            # Ensure file is indexed
            if file_path != "<current_file>":
                await agent.lsp_indexer.index_file(file_path)
            
            result = {"analysis_type": analysis_type, "file_path": file_path, "lsp_based": True}
            
            if analysis_type == "structure":
                # Get symbols and document structure from LSP
                symbols = await agent.lsp_indexer.get_symbols(file_path)
                result.update({
                    "symbols": symbols,
                    "classes": [s for s in symbols if s.get("kind") == "class"],
                    "functions": [s for s in symbols if s.get("kind") == "function"],
                    "variables": [s for s in symbols if s.get("kind") == "variable"],
                    "imports": [s for s in symbols if s.get("kind") == "module"]
                })
                
            elif analysis_type == "dependencies":
                # Get dependencies from LSP
                dependencies = await agent.lsp_indexer.get_dependencies(file_path)
                result.update({
                    "dependencies": dependencies,
                    "imports": dependencies.get("imports", []),
                    "external_deps": dependencies.get("external", []),
                    "internal_deps": dependencies.get("internal", [])
                })
                
            elif analysis_type == "complexity":
                # Use LSP symbols to calculate complexity metrics
                symbols = await agent.lsp_indexer.get_symbols(file_path)
                functions = [s for s in symbols if s.get("kind") == "function"]
                classes = [s for s in symbols if s.get("kind") == "class"]
                
                result.update({
                    "function_count": len(functions),
                    "class_count": len(classes),
                    "total_symbols": len(symbols),
                    "complexity_score": min(10, len(functions) + len(classes) * 2),
                    "functions": [{
                        "name": f.get("name", "unknown"),
                        "line": f.get("line", 0),
                        "complexity": "medium"  # Could be enhanced with more LSP data
                    } for f in functions]
                })
                
            elif analysis_type == "style":
                # Basic style analysis using LSP diagnostics
                diagnostics = await self.agent_integration.lsp_client.get_diagnostics(file_path)
                style_issues = [d for d in diagnostics if d.get("severity") in ["warning", "info"]]
                
                result.update({
                    "style_issues": style_issues,
                    "issue_count": len(style_issues),
                    "suggestions": [issue.get("message", "") for issue in style_issues[:5]]
                })
                
            elif analysis_type == "security":
                # Security analysis using LSP diagnostics
                diagnostics = await self.agent_integration.lsp_client.get_diagnostics(file_path)
                security_issues = [d for d in diagnostics if "security" in d.get("message", "").lower()]
                
                result.update({
                    "security_issues": security_issues,
                    "issue_count": len(security_issues),
                    "recommendations": [issue.get("message", "") for issue in security_issues]
                })
            
            return result
        except ImportError:
            return None
            


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
        
        except AttributeError as e:
            error_msg = f"Editor not available for code insertion: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}
        except ValueError as e:
            error_msg = f"Invalid line number for insertion: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
    async def replace_code(self, start_line: int, end_line: int, new_code: str) -> Dict[str, Any]:
        """Replace code at specific lines in the editor."""
        try:
            if not self.editor:
                return {"error": "No editor available"}
            
            lines = self.editor.text.splitlines()
            
            # Validate line numbers (1-based indexing)
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return {"error": f"Invalid line range: {start_line}-{end_line}"}
            
            # Convert to 0-based indexing
            start_idx = start_line - 1
            end_idx = end_line
            
            # Split new code into lines
            new_lines = new_code.splitlines()
            
            # Replace the specified lines
            lines[start_idx:end_idx] = new_lines
            
            # Update editor content
            self.editor.text = '\n'.join(lines)
            self.editor.is_modified = True
            
            return {
                "success": True,
                "message": f"Code replaced at lines {start_line}-{end_line}",
                "start_line": start_line,
                "end_line": end_line,
                "replaced_lines": end_line - start_line + 1,
                "new_lines": len(new_lines)
            }
        
        except AttributeError as e:
            error_msg = f"Editor not available for code replacement: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}
        except ValueError as e:
            error_msg = f"Invalid line range for replacement: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read content from a file."""
        try:
            file_path = Path(path)
            
            # Validate file exists
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            
            if not file_path.is_file():
                return {"error": f"Path is not a file: {path}"}
            
            # Check file size to avoid reading huge files
            file_size = file_path.stat().st_size
            max_size = 10 * 1024 * 1024  # 10MB limit
            
            if file_size > max_size:
                return {"error": f"File too large ({file_size} bytes). Maximum size is {max_size} bytes."}
            
            # Read file content
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            return {
                "success": True,
                "path": str(file_path),
                "content": content,
                "size": file_size,
                "lines": len(content.splitlines())
            }
        
        except (UnicodeDecodeError, PermissionError, FileNotFoundError, IsADirectoryError) as e:
            error_type = type(e).__name__
            if isinstance(e, UnicodeDecodeError):
                error_msg = f"File is not a text file: {path}"
            elif isinstance(e, PermissionError):
                error_msg = f"Permission denied reading file: {path}"
            elif isinstance(e, FileNotFoundError):
                error_msg = f"File not found: {path}"
            else:  # IsADirectoryError
                error_msg = f"Path is a directory, not a file: {path}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
    async def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            file_path = Path(path)
            
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # Get file info after writing
            file_size = file_path.stat().st_size
            lines = len(content.splitlines())
            
            return {
                "success": True,
                "path": str(file_path),
                "size": file_size,
                "lines": lines,
                "message": f"File written successfully: {path}"
            }
        
        except (PermissionError, IsADirectoryError, OSError) as e:
            if isinstance(e, PermissionError):
                error_msg = f"Permission denied writing to file: {path}"
            elif isinstance(e, IsADirectoryError):
                error_msg = f"Cannot write to directory: {path}"
            else:  # OSError
                error_msg = f"OS error writing file {path}: {e}"
            await self.logger.error(error_msg)
            return {"error": error_msg}

    
    async def _analyze_structure(self, code: str, file_path: str) -> Dict[str, Any]:
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
            "file_path": file_path,
            "lsp_based": False,
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
    
    async def _analyze_dependencies(self, code: str, file_path: str) -> Dict[str, Any]:
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
            "file_path": file_path,
            "lsp_based": False,
            "dependencies": sorted(list(dependencies)),
            "import_statements": imports,
            "dependency_count": len(dependencies)
        }
    
    async def _analyze_complexity(self, code: str, file_path: str) -> Dict[str, Any]:
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
            "file_path": file_path,
            "lsp_based": False,
            "metrics": complexity_indicators,
            "complexity_score": complexity_score,
            "complexity_level": "low" if complexity_score < 10 else "medium" if complexity_score < 25 else "high"
        }
    
    async def _analyze_style(self, code: str, file_path: str) -> Dict[str, Any]:
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
            "file_path": file_path,
            "lsp_based": False,
            "issues": issues,
            "issue_count": len(issues),
            "style_score": max(0, 100 - len(issues) * 2)  # Simple scoring
        }
    
    async def _analyze_security(self, code: str, file_path: str) -> Dict[str, Any]:
        """Analyze potential security issues."""
        security_patterns = {
            "eval_usage": r'\beval\s*\(',
            "exec_usage": r'\bexec\s*\(',
            "shell_injection": r'os\.system\s*\(|subprocess\.[^\s]*\s*\([^)]*shell\s*=\s*True',
            "hardcoded_secrets": r'(?i)(password|secret|key|token)\s*=\s*["\'][^"\']{8,}["\']',
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
            "file_path": file_path,
            "lsp_based": False,
            "issues": issues,
            "issue_count": len(issues),
            "security_score": max(0, 100 - len(issues) * 10)  # Harsh penalty for security issues
        }