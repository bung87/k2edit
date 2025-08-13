"""Search manager for K2Edit"""

import re
import aiofiles
from typing import List, Tuple, Optional
from pathlib import Path
import multiprocessing as mp
from functools import partial
from .async_performance_utils import get_thread_pool


class SearchMatch:
    """Represents a search match."""
    
    def __init__(self, start_line: int, start_col: int, end_line: int, end_col: int, text: str):
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.text = text
    
    def __repr__(self):
        return f"SearchMatch({self.start_line}:{self.start_col}-{self.end_line}:{self.end_col}, '{self.text}')"


class FileSearchResult:
    """Represents search results in a file."""
    
    def __init__(self, file_path: str, matches: List[Tuple[int, int, str]]):
        self.file_path = file_path
        self.matches = matches  # List of (line_number, column, matched_text)
    
    def __repr__(self):
        return f"FileSearchResult({self.file_path}, {len(self.matches)} matches)"


def _search_file_chunk(file_chunk: List[Path], pattern: str, case_sensitive: bool, regex: bool) -> List[FileSearchResult]:
    """Worker function for multiprocessing file search."""
    results = []
    
    for file_path in file_chunk:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Create a temporary SearchManager instance for pattern matching
            temp_manager = SearchManager()
            matches = temp_manager.search_in_text(content, pattern, case_sensitive, regex)
            
            if matches:
                # Convert SearchMatch objects to simple tuples for FileSearchResult
                file_matches = [(match.start_line + 1, match.start_col, match.text) 
                              for match in matches]
                results.append(FileSearchResult(str(file_path), file_matches))
        
        except (UnicodeDecodeError, PermissionError, OSError):
            # Skip files that can't be read
            continue
        except Exception:
            # Skip files with other errors
            continue
    
    return results


class SearchManager:
    """Manages search and replace operations."""
    
    def __init__(self, logger=None):
        self.logger = logger
        self.current_matches = []
        self.current_match_index = -1
        self.last_search_pattern = ""
        self.last_search_options = {}
    
    def search_in_text(self, text: str, pattern: str, case_sensitive: bool = False, 
                      regex: bool = False) -> List[SearchMatch]:
        """Search for pattern in text and return all matches."""
        if not pattern:
            return []
        
        matches = []
        lines = text.split('\n')
        
        try:
            if regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)
            else:
                # Escape special regex characters for literal search
                escaped_pattern = re.escape(pattern)
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(escaped_pattern, flags)
            
            for line_idx, line in enumerate(lines):
                for match in compiled_pattern.finditer(line):
                    start_col = match.start()
                    end_col = match.end()
                    matched_text = match.group()
                    
                    matches.append(SearchMatch(
                        start_line=line_idx,
                        start_col=start_col,
                        end_line=line_idx,
                        end_col=end_col,
                        text=matched_text
                    ))
        
        except re.error as e:
            if self.logger:
                self.logger.error(f"Regex error in search: {e}")
            return []
        
        return matches
    
    def find_next_match(self, text: str, pattern: str, current_line: int, current_col: int,
                       case_sensitive: bool = False, regex: bool = False) -> Optional[SearchMatch]:
        """Find the next match after the current cursor position."""
        matches = self.search_in_text(text, pattern, case_sensitive, regex)
        
        if not matches:
            return None
        
        # Find the first match after current position
        for match in matches:
            if (match.start_line > current_line or 
                (match.start_line == current_line and match.start_col > current_col)):
                return match
        
        # If no match found after current position, wrap to beginning
        return matches[0] if matches else None
    
    def find_previous_match(self, text: str, pattern: str, current_line: int, current_col: int,
                           case_sensitive: bool = False, regex: bool = False) -> Optional[SearchMatch]:
        """Find the previous match before the current cursor position."""
        matches = self.search_in_text(text, pattern, case_sensitive, regex)
        
        if not matches:
            return None
        
        # Find the last match before current position
        for match in reversed(matches):
            if (match.start_line < current_line or 
                (match.start_line == current_line and match.start_col < current_col)):
                return match
        
        # If no match found before current position, wrap to end
        return matches[-1] if matches else None
    
    def replace_in_text(self, text: str, pattern: str, replacement: str, 
                       case_sensitive: bool = False, regex: bool = False, 
                       replace_all: bool = False, current_line: int = 0, 
                       current_col: int = 0) -> Tuple[str, int]:
        """Replace pattern in text. Returns (new_text, replacement_count)."""
        if not pattern:
            return text, 0
        
        try:
            if regex:
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(pattern, flags)
            else:
                # Escape special regex characters for literal search
                escaped_pattern = re.escape(pattern)
                flags = 0 if case_sensitive else re.IGNORECASE
                compiled_pattern = re.compile(escaped_pattern, flags)
            
            if replace_all:
                # Replace all occurrences
                new_text, count = compiled_pattern.subn(replacement, text)
                return new_text, count
            else:
                # Replace only the next occurrence after current position
                lines = text.split('\n')
                replacement_count = 0
                
                for line_idx in range(len(lines)):
                    line = lines[line_idx]
                    
                    # Skip lines before current position
                    if line_idx < current_line:
                        continue
                    
                    # For current line, start search from current column
                    start_pos = current_col if line_idx == current_line else 0
                    
                    # Find first match in this line after start_pos
                    match = compiled_pattern.search(line, start_pos)
                    if match:
                        # Replace this match
                        new_line = line[:match.start()] + replacement + line[match.end():]
                        lines[line_idx] = new_line
                        replacement_count = 1
                        break
                
                return '\n'.join(lines), replacement_count
        
        except re.error as e:
            if self.logger:
                self.logger.error(f"Regex error in replace: {e}")
            return text, 0
    
    async def search_in_files(self, root_path: str, pattern: str, file_pattern: str = "*",
                       case_sensitive: bool = False, regex: bool = False) -> List[FileSearchResult]:
        """Search for pattern in multiple files with multiprocessing optimization."""
        results = []
        root = Path(root_path)
        
        if not root.exists():
            return results
        
        try:
            # Handle file patterns
            if file_pattern == "*" or not file_pattern:
                # Search all text files
                file_patterns = ["*.py", "*.js", "*.ts", "*.html", "*.css", "*.md", "*.txt", 
                               "*.json", "*.yaml", "*.yml", "*.xml", "*.nim", "*.c", "*.cpp", 
                               "*.h", "*.hpp", "*.java", "*.go", "*.rs", "*.php", "*.rb"]
            else:
                file_patterns = [p.strip() for p in file_pattern.split(',')]
            
            # Find all matching files
            files_to_search = set()
            for pattern_str in file_patterns:
                for file_path in root.rglob(pattern_str):
                    if file_path.is_file():
                        files_to_search.add(file_path)
            
            files_list = list(files_to_search)
            
            # Use multiprocessing for large file sets (>50 files)
            if len(files_list) > 50:
                results = await self._search_files_multiprocess(files_list, pattern, case_sensitive, regex)
            else:
                # Use async for smaller file sets
                results = await self._search_files_async(files_list, pattern, case_sensitive, regex)
        
        except Exception as e:
            if self.logger:
                await self.logger.error(f"Error in search_in_files: {e}")
        
        return results
    
    async def _search_files_async(self, files_list: List[Path], pattern: str, 
                                 case_sensitive: bool, regex: bool) -> List[FileSearchResult]:
        """Search files using async I/O for smaller file sets."""
        results = []
        
        for file_path in files_list:
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                
                matches = self.search_in_text(content, pattern, case_sensitive, regex)
                if matches:
                    # Convert SearchMatch objects to simple tuples for FileSearchResult
                    file_matches = [(match.start_line + 1, match.start_col, match.text) 
                                  for match in matches]
                    results.append(FileSearchResult(str(file_path), file_matches))
            
            except (UnicodeDecodeError, PermissionError, OSError) as e:
                if self.logger:
                    await self.logger.warning(f"Could not search in file {file_path}: {e}")
                continue
        
        return results
    
    async def _search_files_multiprocess(self, files_list: List[Path], pattern: str,
                                        case_sensitive: bool, regex: bool) -> List[FileSearchResult]:
        """Search files using multiprocessing for large file sets."""
        # Determine optimal number of processes
        num_processes = min(mp.cpu_count(), max(2, len(files_list) // 20))
        
        # Split files into chunks for each process
        chunk_size = max(1, len(files_list) // num_processes)
        file_chunks = [files_list[i:i + chunk_size] for i in range(0, len(files_list), chunk_size)]
        
        # Create partial function with search parameters
        search_func = partial(_search_file_chunk, pattern=pattern, 
                             case_sensitive=case_sensitive, regex=regex)
        
        # Execute optimized search using thread pool for I/O-bound operations
        thread_pool = get_thread_pool()
        chunk_results = []
        for chunk in file_chunks:
            result = await thread_pool.run_io_bound(search_func, chunk)
            chunk_results.append(result)
        
        # Flatten results from all chunks
        results = []
        for chunk_result in chunk_results:
            results.extend(chunk_result)
        
        return results
    
    def highlight_matches(self, text: str, pattern: str, case_sensitive: bool = False, 
                         regex: bool = False) -> List[Tuple[int, int]]:
        """Return list of (start_offset, end_offset) for highlighting matches."""
        matches = self.search_in_text(text, pattern, case_sensitive, regex)
        highlights = []
        
        lines = text.split('\n')
        current_offset = 0
        
        for line_idx, line in enumerate(lines):
            for match in matches:
                if match.start_line == line_idx:
                    start_offset = current_offset + match.start_col
                    end_offset = current_offset + match.end_col
                    highlights.append((start_offset, end_offset))
            
            current_offset += len(line) + 1  # +1 for newline character
        
        return highlights