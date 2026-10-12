## Code navigation

The worktree for a task is a directory other than this session's start directory. For a question about code in that worktree, use the tools that take the path in each call: mcp__semble__search with repo set to the worktree path for where something is defined, and mcp__codebase-memory-mcp (index_repository on the worktree path first, then search_graph or trace_path for that project) for callers and relationships. Load their schemas with ToolSearch first. Use rg for text that is not code. Do not read whole files to find a definition.
