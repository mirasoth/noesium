---
name: finalize
version: "1.0.0"
created: "2026-03-04"
author: "NoeAgent Team"
description: "Answer synthesis prompt for final output generation"
required_variables:
  - goal
  - results
template_engine: format
---

# Final Answer Synthesis

Synthesize a comprehensive final answer from all the results gathered.

## Goal

{goal}

## Results

{results}

## Synthesis Guidelines

### Structure Your Answer

1. **Direct Answer**: Lead with the primary finding or answer
2. **Supporting Details**: Provide evidence and context
3. **Key Insights**: Highlight important discoveries
4. **Limitations**: Acknowledge what couldn't be determined
5. **Recommendations**: Suggest next steps if relevant

### Quality Standards

- **Clarity**: Use clear, accessible language
- **Accuracy**: Only include verified information
- **Completeness**: Address all aspects of the original goal
- **Relevance**: Focus on what matters to the user
- **Actionability**: Provide concrete, useful information

### Formatting

- Use markdown for readability
- Include code blocks for technical content
- Add links or references when available
- Structure with headers and bullet points
- Highlight critical findings

## Answer Construction

Build your answer by:

1. Reviewing all gathered results
2. Identifying the most relevant findings
3. Connecting related pieces of information
4. Drawing conclusions supported by evidence
5. Addressing the original goal directly

## Final Output

Provide a clear, well-structured answer that:
- Directly addresses the user's goal
- Synthesizes information from multiple sources
- Presents findings in an organized, readable format
- Adds value through insight and context
- Remains focused and relevant