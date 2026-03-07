"""Legacy filename retained; local tools were replaced by toolkit-based tools."""

from noeagent.state import TaskPlan, TaskStep


def test_taskplan_todo_markdown_still_available():
    plan = TaskPlan(goal="x", steps=[TaskStep(description="y")])
    assert "- [ ] 1. y" in plan.to_todo_markdown()
