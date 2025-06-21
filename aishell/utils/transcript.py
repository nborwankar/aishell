"""LLM transcript logging functionality."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import threading


class LLMTranscriptManager:
    """Manages logging of LLM interactions to a persistent transcript file."""
    
    def __init__(self, transcript_file: str = "LLMTranscript.md"):
        self.transcript_file = Path(transcript_file).resolve()
        self._lock = threading.Lock()
        self._ensure_transcript_exists()
    
    def _ensure_transcript_exists(self):
        """Ensure the transcript file exists and has proper header."""
        if not self.transcript_file.exists():
            with open(self.transcript_file, 'w', encoding='utf-8') as f:
                f.write("# LLM Interaction Transcript\n\n")
                f.write("This file contains a log of all LLM interactions from aishell.\n\n")
                f.write("---\n\n")
    
    def log_interaction(self, query: str, response: str, provider: str, model: Optional[str] = None, usage: Optional[dict] = None):
        """Log a single LLM interaction to the transcript."""
        with self._lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Build the log entry
            entry_lines = [
                f"**{timestamp} | {provider.upper()}" + (f" ({model})" if model else "") + "**",
                "",
                f"**Query:** {query}",
                "",
                f"**Response:**",
                response,
                ""
            ]
            
            # Add usage information if available
            if usage:
                usage_str = ", ".join([f"{k}: {v}" for k, v in usage.items()])
                entry_lines.extend([
                    f"**Usage:** {usage_str}",
                    ""
                ])
            
            entry_lines.append("---")
            entry_lines.append("")
            
            # Append to file
            with open(self.transcript_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(entry_lines))
    
    def log_multi_interaction(self, query: str, responses: List[tuple], timestamp: Optional[str] = None):
        """Log a multi-LLM interaction (collation) to the transcript."""
        with self._lock:
            if not timestamp:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            providers_list = [provider for provider, _ in responses]
            providers_str = ", ".join(providers_list)
            
            entry_lines = [
                f"**{timestamp} | COLLATION ({providers_str})**",
                "",
                f"**Query:** {query}",
                "",
                f"**Responses:**",
                ""
            ]
            
            # Add each response
            for provider, response_data in responses:
                entry_lines.extend([
                    f"### {provider.upper()}",
                    ""
                ])
                
                if hasattr(response_data, 'is_error') and response_data.is_error:
                    entry_lines.extend([
                        f"*Error: {response_data.error}*",
                        ""
                    ])
                else:
                    content = response_data.content if hasattr(response_data, 'content') else str(response_data)
                    entry_lines.extend([
                        content,
                        ""
                    ])
                    
                    # Add usage if available
                    if hasattr(response_data, 'usage') and response_data.usage:
                        usage_str = ", ".join([f"{k}: {v}" for k, v in response_data.usage.items()])
                        entry_lines.extend([
                            f"*Usage: {usage_str}*",
                            ""
                        ])
            
            entry_lines.append("---")
            entry_lines.append("")
            
            # Append to file
            with open(self.transcript_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(entry_lines))
    
    def get_transcript_path(self) -> str:
        """Get the full path to the transcript file."""
        return str(self.transcript_file)


# Global transcript manager instance
_transcript_manager = None


def get_transcript_manager() -> LLMTranscriptManager:
    """Get or create the global transcript manager instance."""
    global _transcript_manager
    if _transcript_manager is None:
        _transcript_manager = LLMTranscriptManager()
    return _transcript_manager