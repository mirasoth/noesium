"""Unit tests for Noe task planning helpers and Rich TUI components."""

from noeagent.state import TaskPlan, TaskStep


def test_taskplan_todo_markdown_marks_completed_steps():
    plan = TaskPlan(
        goal="Ship feature",
        steps=[
            TaskStep(description="Design", status="completed"),
            TaskStep(description="Implement", status="pending"),
        ],
    )

    markdown = plan.to_todo_markdown()

    assert "# Todo for: Ship feature" in markdown
    assert "- [x] 1. Design" in markdown
    assert "- [ ] 2. Implement" in markdown


def test_taskplan_advance():
    plan = TaskPlan(
        goal="Do things",
        steps=[
            TaskStep(description="Step A"),
            TaskStep(description="Step B"),
        ],
    )
    assert plan.current_step.description == "Step A"
    assert not plan.is_complete

    plan.advance()
    assert plan.steps[0].status == "completed"
    assert plan.current_step.description == "Step B"

    plan.advance()
    assert plan.is_complete


def test_render_plan_table_columns():
    from noeagent.tui import render_plan_table

    plan = TaskPlan(
        goal="Build app",
        steps=[
            TaskStep(description="Setup", status="completed"),
            TaskStep(description="Code", status="in_progress"),
        ],
    )
    table = render_plan_table(plan)
    assert table.row_count == 2
    assert len(table.columns) == 3


def test_render_plan_tree():
    from noeagent.tui import render_plan_tree
    from rich.tree import Tree as RichTree

    plan = TaskPlan(
        goal="Build app",
        steps=[
            TaskStep(description="Setup", status="completed"),
            TaskStep(description="Code", status="in_progress"),
        ],
    )
    tree = render_plan_tree(plan)
    assert isinstance(tree, RichTree)
    assert "Plan: Build app" in str(tree.label)
    assert tree.children is not None
    assert len(tree.children) == 2


def test_slash_commands_constant():
    from noeagent.tui import SLASH_COMMANDS

    assert "/exit" in SLASH_COMMANDS
    assert "/quit" in SLASH_COMMANDS
    assert "/mode" in SLASH_COMMANDS
    assert "/plan" in SLASH_COMMANDS
    assert "/help" in SLASH_COMMANDS
    assert "/clear" in SLASH_COMMANDS
    assert "/memory" in SLASH_COMMANDS
    assert "/session" in SLASH_COMMANDS
