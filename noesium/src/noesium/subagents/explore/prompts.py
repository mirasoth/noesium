"""General-purpose prompts for ExploreAgent.

Domain-agnostic prompts for exploration across files, documents, data, and media.
"""

EXPLORE_SYSTEM_PROMPT = """You are an expert exploration agent capable of gathering and synthesizing information from diverse sources.

Your responsibilities:
1. Analyze exploration targets
2. Develop effective search strategies
3. Gather information from multiple source types
4. Evaluate completeness of findings
5. Synthesize clear, actionable summaries

You work across source types including:
- Files and code (source code, configuration, scripts)
- Documents (PDFs, Word docs, text files, markdown)
- Data (CSV, Excel, databases, JSON)
- Media (images, audio, video)
- Structured content (APIs, logs, outputs)

Guidelines:
- Identify the target type before exploring
- Use appropriate tools for each source type
- Track all sources and citations
- Evaluate relevance of each finding
- Reflect on completeness before synthesizing
- Provide confidence scores for findings

You have access to:
- File operations (read_file, list_files, search_in_files, get_file_info)
- Shell commands (read-only: ls, cat, head, tail, grep, find)
- Python execution (read-only analysis)
- Document parsing (PDF, Word)
- Media analysis (audio transcription, image analysis, video analysis)
- Data analysis (CSV, Excel, tabular data)

You do NOT have write access - you only gather information.
"""

TARGET_ANALYSIS_PROMPT = """Analyze the following exploration target.

Target: {target}

Context: {context}

Determine:
1. Target type (code, document, data, media, general)
2. What information is being sought
3. Which tools would be most effective
4. What sources should be prioritized
5. Appropriate exploration depth (1-5)

Respond with a JSON object containing:
- target_type: one of "code", "document", "data", "media", "general"
- information_sought: string describing what to find
- recommended_tools: list of tool names
- priority_sources: list of sources to check first
- exploration_depth: integer 1-5
- reasoning: string explaining your analysis
"""

STRATEGY_GENERATION_PROMPT = """Create an exploration strategy for the target.

Target: {target}

Analysis: {analysis}

Create a search strategy with:
1. Specific search queries to run
2. Files or directories to explore
3. Commands to execute
4. Priority ordering
5. Parallel execution paths where possible

For each query, specify:
- query_id: unique identifier
- query: the search query or path
- query_type: file_search, content_search, pattern_match, or analysis
- priority: high, medium, or low
- expected_findings: what we expect to find
"""

REFLECTION_PROMPT = """Reflect on the exploration progress.

Target: {target}

Findings so far:
{findings}

Sources accessed:
{sources}

Current loop: {current_loop}/{max_loops}

Evaluate:
1. Is the gathered information sufficient to answer the exploration target?
2. What knowledge gaps remain?
3. What follow-up queries would fill those gaps?
4. Confidence level in current findings (0.0 to 1.0)

Respond with a JSON object containing:
- is_sufficient: boolean
- knowledge_gaps: list of strings
- follow_up_queries: list of strings
- confidence: float 0.0-1.0
- reasoning: string explaining your assessment

Be honest about gaps. If important information is missing, mark as insufficient.
"""

SYNTHESIS_PROMPT = """Synthesize all findings into a comprehensive summary.

Target: {target}

Findings:
{findings}

Sources:
{sources}

Exploration depth: {exploration_depth}

Create a clear, organized summary that:
1. Directly addresses the exploration target
2. Highlights key findings with their relevance (high/medium/low)
3. Provides actionable insights
4. References specific sources for each finding
5. Notes any gaps or limitations
6. Includes an overall confidence score (0.0-1.0)

Structure the summary with:
- Executive Summary (1-2 sentences)
- Key Findings (bullet points with source citations)
- Detailed Analysis (organized by topic)
- Limitations and Gaps
- Confidence Assessment
"""

FINDING_EXTRACTION_PROMPT = """Extract structured findings from the exploration results.

Raw Results:
{raw_results}

Source: {source}

For each distinct finding, provide:
- finding_id: unique identifier (e.g., "finding-001")
- title: brief title (max 10 words)
- description: detailed description
- source: where this came from
- relevance: high, medium, or low
- finding_type: fact, pattern, insight, or reference
- details: any additional structured data

Focus on findings that are:
- Directly relevant to the exploration target
- Actionable or informative
- Well-supported by the source material
"""

SOURCE_TRACKING_PROMPT = """Document the source that was accessed.

Source Information:
- Path/Location: {location}
- Content Summary: {content_summary}
- Access Method: {access_method}

Create a source record with:
- source_id: unique identifier
- type: file, document, data, media, or url
- name: display name
- location: full path or URL
- summary: brief summary of what this source contains
- accessed_at: current timestamp
"""
