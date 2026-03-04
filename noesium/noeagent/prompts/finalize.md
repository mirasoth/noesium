---
name: finalize
version: "1.3.1"
created: "2026-03-04"
modified: "2026-03-04"
author: "NoeAgent Team"
description: "Answer synthesis prompt for adaptive final output generation"
required_variables:
  - goal
  - results
optional_variables:
  current_datetime: ""
template_engine: format
---

## Goal

{goal}

## Results

{results}

## Context

Current date and time (use when discussing time-sensitive or future-dated sources): {current_datetime}

## Quality and Safety

- **Accuracy**: Only include information supported by the gathered results. Do not fabricate URLs, numbers, or facts.
- **Sources**: When results came from web search or external sources, include a "Sources" or "References" section as appropriate to the report depth (see below).
- **Date consistency**: If any cited material shows dates after the current date, state that clearly and treat it as unreliable (simulation, error, or hypothetical). Do not present future-dated content as current fact.
- **Limitations**: Note what could not be determined only when relevant to the chosen report depth.

## Adaptive Report Depth

**Choose one tier** based on the goal and the amount/diversity of results. Then produce the final output in that format.

### 1. Simple (brief answer)

- **When**: Single, focused question; few results; user likely wants a quick answer (e.g. "What is X?", "Latest development in one sentence", "Brief summary").
- **Format**: One short paragraph or a few bullet points. Direct answer only. Omit Sources/Limitations unless critical (e.g. date inconsistency or single key caveat).

### 2. Complex (detailed answer)

- **When**: Multi-part question, or many findings, or need to compare/explain several aspects.
- **Format**: 1) Direct answer; 2) Supporting details; 3) Key insights. Add a short **Sources** section if results came from web/external sources. Add **Limitations** only if relevant (e.g. conflicting sources, missing data, date issues).

### 3. Deep research (full report)

- **When**: Open-ended research, in-depth or multi-source investigation, many steps/sources, or goal explicitly asks for a report or comprehensive analysis.
- **Format**: 1) **Executive summary** (2–3 sentences); 2) **Direct answer**; 3) **Supporting details / evidence**; 4) **Key insights**; 5) **Sources (References)** with links; 6) **Limitations**; 7) **Recommendations** (optional, only if useful).

## Final Output

- Apply the chosen tier above. Do not pad simple questions with a full report; do not truncate deep research into one paragraph.
- Use markdown for readability; use code blocks for technical content; cite sources when applicable. Do not give time estimates.