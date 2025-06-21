import os
import re
import subprocess
import shlex
from pathlib import Path
from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.panel import Panel
from rich.tree import Tree

console = Console()


class MacOSFileSearcher:
    """macOS-optimized file system search using native tools."""
    
    def __init__(self):
        self.is_macos = self._check_macos()
        self.spotlight_available = self._check_spotlight()
        
    def _check_macos(self) -> bool:
        """Check if running on macOS."""
        return os.uname().sysname == 'Darwin'
    
    def _check_spotlight(self) -> bool:
        """Check if Spotlight (mdfind) is available."""
        try:
            subprocess.run(['mdfind', '--help'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def search_files(
        self,
        pattern: str,
        path: str = ".",
        content_pattern: Optional[str] = None,
        file_type: Optional[str] = None,
        size_filter: Optional[str] = None,
        date_filter: Optional[str] = None,
        ignore_case: bool = True,
        max_results: int = 1000,
        use_spotlight: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for files using macOS native tools.
        
        Args:
            pattern: File name pattern (supports wildcards)
            path: Starting directory path
            content_pattern: Text to search within files
            file_type: Filter by file type/extension
            size_filter: Size filter (e.g., '>1MB', '<500KB')
            date_filter: Date filter (e.g., 'today', 'last week')
            ignore_case: Case-insensitive search
            max_results: Maximum number of results
            use_spotlight: Use Spotlight (mdfind) if available
        """
        if use_spotlight and self.spotlight_available:
            return self._search_with_spotlight(
                pattern, path, content_pattern, file_type, 
                size_filter, date_filter, max_results
            )
        else:
            return self._search_with_find(
                pattern, path, content_pattern, file_type,
                size_filter, date_filter, ignore_case, max_results
            )
    
    def _search_with_spotlight(
        self,
        pattern: str,
        path: str,
        content_pattern: Optional[str],
        file_type: Optional[str],
        size_filter: Optional[str],
        date_filter: Optional[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Use Spotlight (mdfind) for search."""
        query_parts = []
        
        # File name pattern
        if pattern != "*":
            query_parts.append(f"kMDItemDisplayName == '*{pattern}*'")
        
        # Content search
        if content_pattern:
            query_parts.append(f"kMDItemTextContent == '*{content_pattern}*'")
        
        # File type filter
        if file_type:
            type_queries = self._build_type_query(file_type)
            if type_queries:
                query_parts.extend(type_queries)
        
        # Build mdfind command
        cmd = ['mdfind']
        
        # Add directory scope
        if path != ".":
            abs_path = str(Path(path).resolve())
            cmd.extend(['-onlyin', abs_path])
        
        # Add query
        if query_parts:
            full_query = ' && '.join(f"({q})" for q in query_parts)
            cmd.append(full_query)
        else:
            cmd.append('*')  # Search everything
        
        return self._execute_search_command(cmd, max_results, content_pattern)
    
    def _search_with_find(
        self,
        pattern: str,
        path: str,
        content_pattern: Optional[str],
        file_type: Optional[str],
        size_filter: Optional[str],
        date_filter: Optional[str],
        ignore_case: bool,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Use BSD find command for search."""
        cmd = ['find', str(Path(path).resolve())]
        
        # File name pattern
        if pattern != "*":
            if ignore_case:
                cmd.extend(['-iname', pattern])
            else:
                cmd.extend(['-name', pattern])
        
        # File type
        if file_type:
            if file_type == 'directory':
                cmd.extend(['-type', 'd'])
            elif file_type == 'file':
                cmd.extend(['-type', 'f'])
            else:
                # File extension
                cmd.extend(['-name', f'*.{file_type}'])
        
        # Size filter
        if size_filter:
            size_args = self._parse_size_for_find(size_filter)
            cmd.extend(['-size', size_args])
        
        # Date filter
        if date_filter:
            date_args = self._parse_date_for_find(date_filter)
            cmd.extend(date_args)
        
        # Exclude common directories
        excludes = ['.git', '__pycache__', 'node_modules', '.DS_Store']
        for exclude in excludes:
            cmd.extend(['!', '-path', f'*/{exclude}/*'])
        
        return self._execute_search_command(cmd, max_results, content_pattern)
    
    def _execute_search_command(
        self, 
        cmd: List[str], 
        max_results: int,
        content_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Execute search command and process results."""
        results = []
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Searching with native tools...", total=None)
                
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30  # Prevent hanging
                )
                
                if process.returncode != 0:
                    console.print(f"[red]Search command failed: {process.stderr}[/red]")
                    return results
                
                lines = process.stdout.strip().split('\n')
                
                for i, line in enumerate(lines):
                    if i >= max_results:
                        break
                    
                    if not line:
                        continue
                    
                    file_path = Path(line)
                    
                    # Update progress
                    progress.update(task, description=f"Processing: {file_path.name}")
                    
                    try:
                        if not file_path.exists():
                            continue
                        
                        stat = file_path.stat()
                        
                        # Content search with grep if needed
                        matches = []
                        if content_pattern and file_path.is_file():
                            matches = self._grep_content(file_path, content_pattern)
                        
                        result = {
                            'path': str(file_path),
                            'name': file_path.name,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime),
                            'is_dir': file_path.is_dir(),
                            'matches': matches
                        }
                        
                        # Get additional macOS metadata
                        if self.is_macos:
                            result.update(self._get_macos_metadata(file_path))
                        
                        results.append(result)
                        
                    except Exception as e:
                        # Skip problematic files
                        continue
                        
        except subprocess.TimeoutExpired:
            console.print("[red]Search timed out[/red]")
        except Exception as e:
            console.print(f"[red]Search error: {e}[/red]")
        
        return results
    
    def _build_type_query(self, file_type: str) -> List[str]:
        """Build Spotlight queries for file types."""
        type_mappings = {
            'image': ['kMDItemContentType == "public.image"'],
            'video': ['kMDItemContentType == "public.movie"'],
            'audio': ['kMDItemContentType == "public.audio"'],
            'text': ['kMDItemContentType == "public.text"'],
            'pdf': ['kMDItemContentType == "com.adobe.pdf"'],
            'code': [
                'kMDItemContentType == "public.source-code"',
                'kMDItemDisplayName == "*.py"',
                'kMDItemDisplayName == "*.js"',
                'kMDItemDisplayName == "*.ts"',
                'kMDItemDisplayName == "*.java"',
                'kMDItemDisplayName == "*.c"',
                'kMDItemDisplayName == "*.cpp"'
            ]
        }
        
        if file_type in type_mappings:
            return type_mappings[file_type]
        else:
            # Treat as file extension
            return [f'kMDItemDisplayName == "*.{file_type}"']
    
    def _parse_size_for_find(self, size_filter: str) -> str:
        """Parse size filter for find command."""
        # Convert human readable to find format
        # Examples: '>1MB' -> '+1048576c', '<500KB' -> '-512000c'
        
        size_units = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
        
        match = re.match(r'([<>]=?)\s*(\d+(?:\.\d+)?)\s*([KMGT]?B)', size_filter, re.IGNORECASE)
        if match:
            op, val, unit = match.groups()
            bytes_val = int(float(val) * size_units.get(unit.upper(), 1))
            
            if op.startswith('>'):
                return f'+{bytes_val}c'
            else:
                return f'-{bytes_val}c'
        
        return size_filter  # Return as-is if can't parse
    
    def _parse_date_for_find(self, date_filter: str) -> List[str]:
        """Parse date filter for find command."""
        now = datetime.now()
        
        if date_filter.lower() == 'today':
            return ['-mtime', '-1']
        elif date_filter.lower() == 'yesterday':
            return ['-mtime', '1']
        elif date_filter.lower() == 'last week':
            return ['-mtime', '-7']
        elif date_filter.lower() == 'last month':
            return ['-mtime', '-30']
        else:
            # Try parsing as number of days
            try:
                days = int(date_filter)
                return ['-mtime', f'-{days}']
            except ValueError:
                return []
    
    def _grep_content(self, file_path: Path, pattern: str) -> List[Tuple[int, str]]:
        """Use grep to search file content."""
        matches = []
        try:
            cmd = ['grep', '-n', '-i', pattern, str(file_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n')[:10]:  # Limit matches
                    if ':' in line:
                        line_no, content = line.split(':', 1)
                        try:
                            matches.append((int(line_no), content.strip()))
                        except ValueError:
                            continue
        except Exception:
            pass
        
        return matches
    
    def _get_macos_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Get additional macOS metadata using mdls."""
        metadata = {}
        try:
            cmd = ['mdls', '-name', 'kMDItemContentType', 
                   '-name', 'kMDItemKind', 
                   '-name', 'kMDItemLastUsedDate',
                   str(file_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"')
                        
                        if key == 'kMDItemContentType':
                            metadata['content_type'] = value
                        elif key == 'kMDItemKind':
                            metadata['kind'] = value
                        elif key == 'kMDItemLastUsedDate':
                            metadata['last_used'] = value
        except Exception:
            pass
        
        return metadata
    
    def quick_search(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Quick Spotlight search for any query."""
        if not self.spotlight_available:
            console.print("[yellow]Spotlight not available, falling back to find[/yellow]")
            return self._search_with_find(query, ".", None, None, None, None, True, max_results)
        
        cmd = ['mdfind', '-limit', str(max_results), query]
        return self._execute_search_command(cmd, max_results)


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def format_date(date: datetime) -> str:
    """Format date in relative or absolute format."""
    now = datetime.now()
    diff = now - date
    
    if diff.days == 0:
        if diff.seconds < 3600:
            return f"{diff.seconds // 60} minutes ago"
        else:
            return f"{diff.seconds // 3600} hours ago"
    elif diff.days == 1:
        return "yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    else:
        return date.strftime("%Y-%m-%d %H:%M")


def display_results(results: List[Dict[str, Any]], show_content: bool = True):
    """Display search results in a formatted manner."""
    if not results:
        console.print("[yellow]No files found matching the criteria.[/yellow]")
        return
    
    # Create results table
    table = Table(title=f"Found {len(results)} files", show_lines=True)
    table.add_column("Path", style="cyan", no_wrap=False)
    table.add_column("Size", style="green", width=10)
    table.add_column("Modified", style="blue", width=20)
    
    for result in results[:50]:  # Show first 50 in table
        table.add_row(
            result['path'],
            format_size(result['size']),
            format_date(result['modified'])
        )
    
    console.print(table)
    
    if len(results) > 50:
        console.print(f"\n[dim]... and {len(results) - 50} more files[/dim]")
    
    # Show content matches if any
    if show_content:
        for result in results[:10]:  # Show content for first 10 files
            if result.get('matches'):
                panel_content = ""
                for line_no, line in result['matches'][:5]:
                    panel_content += f"[dim]{line_no:4d}:[/dim] {line}\n"
                
                if len(result['matches']) > 5:
                    panel_content += f"[dim]... and {len(result['matches']) - 5} more matches[/dim]"
                
                console.print(Panel(
                    panel_content,
                    title=f"[bold]{result['path']}[/bold]",
                    expand=False
                ))


def create_tree_view(results: List[Dict[str, Any]], root_path: str = ".") -> Tree:
    """Create a tree view of search results."""
    tree = Tree(f"[bold]{root_path}[/bold]")
    
    # Build tree structure
    paths = {}
    for result in results:
        parts = Path(result['path']).parts
        current = tree
        
        for i, part in enumerate(parts[:-1]):
            path_key = '/'.join(parts[:i+1])
            if path_key not in paths:
                paths[path_key] = current.add(f"📁 {part}")
            current = paths[path_key]
        
        # Add file
        file_icon = "📄" if not result['is_dir'] else "📁"
        size_str = format_size(result['size'])
        current.add(f"{file_icon} {parts[-1]} [dim]({size_str})[/dim]")
    
    return tree


# Convenience alias for backwards compatibility
FileSearcher = MacOSFileSearcher