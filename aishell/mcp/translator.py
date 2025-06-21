"""Natural language to MCP message translator."""

import re
from typing import Dict, Any, Optional, List, Tuple
from ..llm import LLMProvider, ClaudeLLMProvider, OpenAILLMProvider
from .client import MCPMessage, MCPMethod


class NLToMCPTranslator:
    """Translates natural language queries to MCP messages."""
    
    # Common patterns for different MCP operations
    PATTERNS = {
        'list_tools': [
            r'(list|show|get|what).*(tools?|functions?|capabilities)',
            r'what can (you|the server) do',
            r'available (tools?|functions?)',
        ],
        'call_tool': [
            r'(call|run|execute|use)\s+(?:the\s+)?(\w+)\s+(?:tool|function)',
            r'(\w+)\s+tool\s+with',
            r'use\s+(\w+)\s+to',
        ],
        'list_resources': [
            r'(list|show|get|what).*(resources?|files?|data)',
            r'available (resources?|files?)',
        ],
        'read_resource': [
            r'(read|get|show|fetch)\s+(?:the\s+)?(?:resource|file)\s+(.+)',
            r'(read|get|show)\s+(.+)\s+(?:resource|file)',
        ],
        'list_prompts': [
            r'(list|show|get|what).*(prompts?|templates?)',
            r'available (prompts?|templates?)',
        ],
        'get_prompt': [
            r'(get|show|use)\s+(?:the\s+)?(\w+)\s+prompt',
            r'prompt\s+(?:named\s+)?(\w+)',
        ],
        'ping': [
            r'ping',
            r'test connection',
            r'check server',
        ],
    }
    
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        """Initialize the translator.
        
        Args:
            llm_provider: Optional LLM provider for advanced translation
        """
        self.llm_provider = llm_provider
    
    def extract_json_args(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON arguments from text.
        
        Args:
            text: Text containing potential JSON
            
        Returns:
            Extracted JSON as dict or None
        """
        import json
        
        # Look for JSON-like content between braces
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Look for key=value pairs
        pairs = re.findall(r'(\w+)=(["\']?)([^"\'\s]+)\2', text)
        if pairs:
            return {k: v for k, _, v in pairs}
        
        return None
    
    def parse_simple_query(self, query: str) -> Optional[MCPMessage]:
        """Parse simple queries using pattern matching.
        
        Args:
            query: Natural language query
            
        Returns:
            MCPMessage if pattern matches, None otherwise
        """
        query_lower = query.lower().strip()
        
        # Check each pattern type
        for operation, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    if operation == 'list_tools':
                        return MCPMessage(method=MCPMethod.TOOLS_LIST.value)
                    
                    elif operation == 'call_tool':
                        # Extract tool name and arguments
                        groups = match.groups()
                        tool_name = groups[-1] if groups else None
                        
                        if tool_name:
                            # Look for arguments
                            args = self.extract_json_args(query)
                            return MCPMessage(
                                method=MCPMethod.TOOLS_CALL.value,
                                params={
                                    "name": tool_name,
                                    "arguments": args or {}
                                }
                            )
                    
                    elif operation == 'list_resources':
                        return MCPMessage(method=MCPMethod.RESOURCES_LIST.value)
                    
                    elif operation == 'read_resource':
                        groups = match.groups()
                        resource_uri = groups[-1] if groups else None
                        
                        if resource_uri:
                            return MCPMessage(
                                method=MCPMethod.RESOURCES_READ.value,
                                params={"uri": resource_uri.strip()}
                            )
                    
                    elif operation == 'list_prompts':
                        return MCPMessage(method=MCPMethod.PROMPTS_LIST.value)
                    
                    elif operation == 'get_prompt':
                        groups = match.groups()
                        prompt_name = groups[-1] if groups else None
                        
                        if prompt_name:
                            args = self.extract_json_args(query)
                            params = {"name": prompt_name}
                            if args:
                                params["arguments"] = args
                            return MCPMessage(
                                method=MCPMethod.PROMPTS_GET.value,
                                params=params
                            )
                    
                    elif operation == 'ping':
                        return MCPMessage(method=MCPMethod.PING.value)
        
        return None
    
    async def translate_with_llm(self, query: str) -> Optional[MCPMessage]:
        """Translate query using LLM.
        
        Args:
            query: Natural language query
            
        Returns:
            MCPMessage or None if translation fails
        """
        if not self.llm_provider:
            return None
        
        prompt = f"""Convert the following natural language query into an MCP (Model Context Protocol) JSON-RPC message.

Available MCP methods:
- tools/list: List available tools
- tools/call: Call a tool (params: name, arguments)
- resources/list: List available resources
- resources/read: Read a resource (params: uri)
- resources/write: Write a resource (params: uri, content)
- prompts/list: List available prompts
- prompts/get: Get a prompt (params: name, arguments)
- ping: Ping the server
- initialize: Initialize connection

Query: {query}

Respond with ONLY the JSON-RPC message object, no explanation. Example:
{{"jsonrpc": "2.0", "method": "tools/list"}}
"""
        
        try:
            response = await self.llm_provider.query(
                prompt,
                temperature=0.3,
                max_tokens=200
            )
            
            if response.is_error:
                return None
            
            # Extract JSON from response
            import json
            # Use a more robust pattern that can handle nested braces
            json_match = re.search(r'\{.*?\}', response.content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return MCPMessage.from_dict(data)
                except json.JSONDecodeError:
                    # Try a broader search for the complete JSON object
                    brace_count = 0
                    start_pos = response.content.find('{')
                    if start_pos != -1:
                        for i, char in enumerate(response.content[start_pos:], start_pos):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_str = response.content[start_pos:i+1]
                                    try:
                                        data = json.loads(json_str)
                                        return MCPMessage.from_dict(data)
                                    except json.JSONDecodeError:
                                        break
                
        except Exception:
            pass
        
        return None
    
    async def translate(self, query: str) -> MCPMessage:
        """Translate natural language to MCP message.
        
        Args:
            query: Natural language query
            
        Returns:
            MCPMessage (may be a custom method if translation fails)
        """
        # First try simple pattern matching
        message = self.parse_simple_query(query)
        if message:
            return message
        
        # Try LLM translation if available
        if self.llm_provider:
            message = await self.translate_with_llm(query)
            if message:
                return message
        
        # Fallback to custom method with the query as parameter
        return MCPMessage(
            method=MCPMethod.CUSTOM.value,
            params={"query": query}
        )
    
    def get_suggestions(self, partial_query: str) -> List[str]:
        """Get query suggestions based on partial input.
        
        Args:
            partial_query: Partial query string
            
        Returns:
            List of suggested completions
        """
        suggestions = []
        partial_lower = partial_query.lower().strip()
        
        # Common query starters
        starters = [
            "list tools",
            "list resources",
            "list prompts",
            "call tool",
            "read resource",
            "get prompt",
            "ping server",
            "use tool",
            "show available tools",
            "what can you do",
        ]
        
        for starter in starters:
            if starter.startswith(partial_lower):
                suggestions.append(starter)
        
        return suggestions[:5]  # Return top 5 suggestions