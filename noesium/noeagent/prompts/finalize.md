---
name: finalize
version: "1.2.0"
created: "2026-03-04"
modified: "2026-03-04"
author: "NoeAgent Team"
description: "Answer synthesis prompt for final output generation"
required_variables:
  - goal
  - results
template_engine: format
---

# Final Answer Synthesis

Synthesize an answer from the gathered results. **Prefer a simple, direct answer.** Use the optional structure below only when the goal or results are complex and need multiple sections.

## Goal

{goal}

## Results

{results}

## Quality and Safety

- **Accuracy**: Only include information supported by the gathered results. Do not fabricate URLs, numbers, or facts.
- **Sources**: When results came from web search or external sources, add a brief "Sources" or "References" section with relevant links.
- **Limitations**: Briefly note what could not be determined only if relevant.

## Final Output

- **Default**: Give a clear, concise answer that directly addresses the goal. One short paragraph or a few bullet points is often enough. Do not pad with extra sections.
- **Only when necessary** (e.g. multi-part research, many findings): you may structure with 1) Direct answer, 2) Supporting details, 3) Key insights, 4) Limitations, 5) Recommendations. Otherwise omit this structure.
- Use markdown for readability; use code blocks for technical content; cite sources when applicable. Do not give time estimates.