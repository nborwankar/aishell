"""MCP server discovery and capability reporting for LLM context."""

from typing import Dict, List, Optional
from .env_manager import get_env_manager


class MCPCapabilityManager:
    """Manages MCP server capabilities and provides context for LLMs."""
    
    def __init__(self):
        self.server_capabilities = {
            'postgres': {
                'description': 'PostgreSQL database access and operations',
                'capabilities': [
                    'Execute SQL queries (SELECT, INSERT, UPDATE, DELETE)',
                    'Schema inspection (tables, columns, indexes)',
                    'Database administration tasks',
                    'Data analysis and reporting'
                ],
                'example_commands': [
                    'mcp postgres "list all tables"',
                    'mcp postgres "show schema for users table"',
                    'mcp postgres "SELECT * FROM orders WHERE date > \'2024-01-01\'"'
                ]
            },
            'sqlite': {
                'description': 'SQLite local database file operations',
                'capabilities': [
                    'Query local SQLite databases',
                    'Table and schema inspection',
                    'Data import/export operations',
                    'Database file management'
                ],
                'example_commands': [
                    'mcp sqlite "list tables"',
                    'mcp sqlite "SELECT COUNT(*) FROM users"',
                    'mcp sqlite "PRAGMA table_info(products)"'
                ]
            },
            'mysql': {
                'description': 'MySQL database connectivity and operations',
                'capabilities': [
                    'Full MySQL query support',
                    'Database and table management',
                    'Performance monitoring',
                    'User and permission management'
                ],
                'example_commands': [
                    'mcp mysql "SHOW DATABASES"',
                    'mcp mysql "SELECT * FROM information_schema.tables"',
                    'mcp mysql "DESCRIBE users"'
                ]
            },
            'github': {
                'description': 'GitHub repository and API management',
                'capabilities': [
                    'Repository browsing and file access',
                    'Issue and pull request management',
                    'Commit history and branch operations',
                    'GitHub Actions workflow management'
                ],
                'example_commands': [
                    'mcp github "list repositories"',
                    'mcp github "show issues for repo/name"',
                    'mcp github "get file content from main branch"'
                ]
            },
            'gitlab': {
                'description': 'GitLab project and CI/CD operations',
                'capabilities': [
                    'Project and repository management',
                    'Merge request operations',
                    'CI/CD pipeline monitoring',
                    'Issue tracking and milestones'
                ],
                'example_commands': [
                    'mcp gitlab "list projects"',
                    'mcp gitlab "show pipeline status"',
                    'mcp gitlab "get merge requests"'
                ]
            },
            'jira': {
                'description': 'JIRA project management and issue tracking',
                'capabilities': [
                    'Issue creation, viewing, and management',
                    'Project and sprint operations',
                    'Workflow and transition management',
                    'Reporting and dashboard access'
                ],
                'example_commands': [
                    'mcp jira "list open issues"',
                    'mcp jira "create new issue with title and description"',
                    'mcp jira "show sprint progress"'
                ]
            },
            'atlassian': {
                'description': 'Full Atlassian suite (Confluence + JIRA)',
                'capabilities': [
                    'All JIRA functionality',
                    'Confluence page management',
                    'Cross-tool integration and linking',
                    'Team collaboration workflows'
                ],
                'example_commands': [
                    'mcp atlassian "search confluence pages"',
                    'mcp atlassian "link jira issue to confluence page"',
                    'mcp atlassian "get team dashboard"'
                ]
            },
            'filesystem': {
                'description': 'Secure file system operations',
                'capabilities': [
                    'File and directory browsing',
                    'File content reading and writing',
                    'File metadata and permissions',
                    'Safe file operations with access controls'
                ],
                'example_commands': [
                    'mcp filesystem "list files in directory"',
                    'mcp filesystem "read file content"',
                    'mcp filesystem "create new file with content"'
                ]
            },
            'fetch': {
                'description': 'Web content fetching and conversion',
                'capabilities': [
                    'HTTP requests to web URLs',
                    'HTML to markdown conversion',
                    'Content extraction and parsing',
                    'Web scraping with rate limiting'
                ],
                'example_commands': [
                    'mcp fetch "get content from https://example.com"',
                    'mcp fetch "convert webpage to markdown"',
                    'mcp fetch "extract text from HTML page"'
                ]
            },
            'memory': {
                'description': 'Persistent knowledge graph storage',
                'capabilities': [
                    'Store and retrieve knowledge entities',
                    'Relationship mapping and queries',
                    'Persistent memory across sessions',
                    'Knowledge graph visualization'
                ],
                'example_commands': [
                    'mcp memory "store fact about user preferences"',
                    'mcp memory "recall information about project X"',
                    'mcp memory "show relationships for entity"'
                ]
            },
            'docker': {
                'description': 'Docker container management',
                'capabilities': [
                    'Container lifecycle management',
                    'Image building and deployment',
                    'Container monitoring and logs',
                    'Docker Compose operations'
                ],
                'example_commands': [
                    'mcp docker "list running containers"',
                    'mcp docker "show container logs"',
                    'mcp docker "start/stop container"'
                ]
            },
            'kubernetes': {
                'description': 'Kubernetes cluster operations',
                'capabilities': [
                    'Pod and deployment management',
                    'Service and ingress configuration',
                    'Cluster monitoring and scaling',
                    'Namespace and resource management'
                ],
                'example_commands': [
                    'mcp kubernetes "list pods in namespace"',
                    'mcp kubernetes "show deployment status"',
                    'mcp kubernetes "scale deployment to 3 replicas"'
                ]
            },
            'aws': {
                'description': 'AWS S3 storage operations',
                'capabilities': [
                    'S3 bucket and object management',
                    'File upload and download',
                    'Access control and permissions',
                    'Storage analytics and monitoring'
                ],
                'example_commands': [
                    'mcp aws "list S3 buckets"',
                    'mcp aws "upload file to bucket"',
                    'mcp aws "download object from S3"'
                ]
            },
            'gcp': {
                'description': 'Google Cloud Platform storage',
                'capabilities': [
                    'Cloud Storage bucket operations',
                    'Object lifecycle management',
                    'Access control and IAM',
                    'Storage monitoring and analytics'
                ],
                'example_commands': [
                    'mcp gcp "list storage buckets"',
                    'mcp gcp "create new bucket"',
                    'mcp gcp "set object permissions"'
                ]
            }
        }
    
    def get_available_servers(self) -> Dict[str, str]:
        """Get currently configured MCP servers."""
        env_manager = get_env_manager()
        return env_manager.get_mcp_servers()
    
    def get_server_capabilities(self, server_name: str) -> Optional[Dict]:
        """Get capabilities for a specific server."""
        return self.server_capabilities.get(server_name)
    
    def generate_mcp_context_prompt(self) -> str:
        """Generate a context prompt for LLMs about available MCP capabilities."""
        available_servers = self.get_available_servers()
        
        if not available_servers:
            return "No MCP servers are currently configured."
        
        context_parts = [
            "AVAILABLE MCP TOOLS AND CAPABILITIES:",
            "",
            "You have access to the following MCP (Model Context Protocol) servers that extend your capabilities:",
            ""
        ]
        
        for server_name, server_command in available_servers.items():
            capabilities = self.get_server_capabilities(server_name)
            if capabilities:
                context_parts.extend([
                    f"## {server_name.upper()} - {capabilities['description']}",
                    f"Command: {server_command}",
                    "",
                    "Capabilities:",
                ])
                
                for capability in capabilities['capabilities']:
                    context_parts.append(f"  • {capability}")
                
                context_parts.extend([
                    "",
                    "Example usage:",
                ])
                
                for example in capabilities['example_commands']:
                    context_parts.append(f"  {example}")
                
                context_parts.extend(["", "---", ""])
        
        context_parts.extend([
            "",
            "USAGE INSTRUCTIONS:",
            "• Use 'mcp <server_name> <command>' to interact with any configured server",
            "• You can suggest MCP operations to users when they ask about tasks these tools can handle",
            "• Always explain what the MCP command will do before suggesting it",
            "• For database queries, be careful with destructive operations (UPDATE, DELETE, DROP)",
            "• When working with external services, consider authentication and permissions",
            "",
            "Example workflow:",
            "1. User asks about database analysis → suggest 'mcp postgres' commands",
            "2. User needs GitHub info → suggest 'mcp github' operations", 
            "3. User wants to manage issues → suggest 'mcp jira' commands",
            ""
        ])
        
        return "\n".join(context_parts)
    
    def get_capability_summary(self) -> Dict[str, List[str]]:
        """Get a summary of all capabilities by category."""
        available_servers = self.get_available_servers()
        
        summary = {}
        for server_name in available_servers.keys():
            capabilities = self.get_server_capabilities(server_name)
            if capabilities:
                summary[server_name] = capabilities['capabilities']
        
        return summary


# Global capability manager instance
_capability_manager = None


def get_mcp_capability_manager() -> MCPCapabilityManager:
    """Get or create the global MCP capability manager instance."""
    global _capability_manager
    if _capability_manager is None:
        _capability_manager = MCPCapabilityManager()
    return _capability_manager