## More Subagents Design

### Princples

- subagents COULD call other subagents or use tools

### Agents

- PlanAgent: a planner reading files and planning for complex task. The agent could use reado-only tools, e.g,
    - read_file, list_files, search_in_files, get_file_info of file_edit_toolkits
    - user_interaction_toolkit
    - could call ExploreAgent

- ExploreAgent: an agent to explore to essential info related to given target. The agent could use reado-only tools, e.g,
    - read_file, list_files, search_in_files, get_file_info of file_edit_toolkits
    - bash toolkits without side-effect (readonly)
    - python_executor_toolkit without side-effect (readonly)
    - document_toolkit without side-effect (readonly)
    - transcribe_audio, get_audio_info of audio_toolkit
    - image_toolkit without side-effect (readonly)
    - video_toolkit
    - tabular_data_toolkit

- Davinci: an agent for scientific reserach. Placeholder for future

### Task

per @docs/drafts/proposal.md and refer to current noeagent about how to use tools, refer to tacitus about how to expose progrese events. Now design and impl these three agents and each with an example to use. Also add unit and integration tests.f