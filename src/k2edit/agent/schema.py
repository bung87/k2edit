"""Tool schemas for Kimi API function calling."""

# Tool schemas that will be sent to Kimi API for function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from disk. Use this to examine existing files before making changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to read (relative or absolute)"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. This will create a new file or overwrite an existing one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file path to write to (relative or absolute)"
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_code",
            "description": "Replace a range of lines in the current editor buffer with new code. Use this to modify existing code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_line": {
                        "type": "integer",
                        "description": "The starting line number (1-based) to replace",
                        "minimum": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "The ending line number (1-based) to replace (inclusive)",
                        "minimum": 1
                    },
                    "new_code": {
                        "type": "string",
                        "description": "The new code to replace the specified lines with"
                    }
                },
                "required": ["start_line", "end_line", "new_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "insert_code",
            "description": "Insert new code at a specific line in the current editor buffer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "description": "The line number (1-based) where to insert the code",
                        "minimum": 1
                    },
                    "code": {
                        "type": "string",
                        "description": "The code to insert"
                    }
                },
                "required": ["line_number", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory. Useful for exploring project structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "The directory path to list (defaults to current directory)",
                        "default": "."
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional file pattern to filter results (e.g., '*.py')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for code patterns or text within files. Useful for finding specific functions or variables.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The text or regex pattern to search for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "File pattern to limit search scope (e.g., '*.py')",
                        "default": "*"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)",
                        "default": "."
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command. Use with caution and prefer file operations when possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Working directory for the command (defaults to current directory)",
                        "default": "."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_code",
            "description": "Analyze code structure, dependencies, or patterns in the current file or selection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform",
                        "enum": ["structure", "dependencies", "complexity", "style", "security"]
                    },
                    "scope": {
                        "type": "string",
                        "description": "Scope of analysis",
                        "enum": ["selection", "file", "project"],
                        "default": "selection"
                    }
                },
                "required": ["analysis_type"]
            }
        }
    }
]

# Tool categories for better organization
TOOL_CATEGORIES = {
    "file_operations": ["read_file", "write_file", "list_files"],
    "code_editing": ["replace_code", "insert_code"],
    "code_analysis": ["search_code", "analyze_code"],
    "system": ["run_command"]
}

# Tool descriptions for help system
TOOL_DESCRIPTIONS = {
    "read_file": "Read file contents",
    "write_file": "Write content to file",
    "replace_code": "Replace lines in editor",
    "insert_code": "Insert code at line",
    "list_files": "List directory contents",
    "search_code": "Search for code patterns",
    "run_command": "Execute shell command",
    "analyze_code": "Analyze code structure"
}