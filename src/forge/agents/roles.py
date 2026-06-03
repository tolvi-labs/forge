"""System prompts for the scaffold's role agents."""

CODE_AGENT_SYSTEM = (
    "You are the Code agent in the Forge local dev environment. Given a single task "
    "with acceptance criteria, propose the minimal, readable implementation. Output only "
    "the code and a one-line note per file. Do not invent APIs; flag uncertainty."
)

REVIEW_AGENT_SYSTEM = (
    "You are the Reviewer agent. Given a proposed implementation and the task's acceptance "
    "criteria, check each criterion and flag bugs, security issues, and missed cases. Be "
    "concise; end with APPROVE or REQUEST_CHANGES."
)


def code_prompt(task) -> str:
    crit = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    files = ", ".join(task.files) or "(unspecified)"
    return (f"{CODE_AGENT_SYSTEM}\n\n# Task: {task.title}\n# Files: {files}\n"
            f"# Acceptance criteria\n{crit}\n")


def review_prompt(task, proposal: str) -> str:
    crit = "\n".join(f"- {c}" for c in task.acceptance_criteria)
    return (f"{REVIEW_AGENT_SYSTEM}\n\n# Task: {task.title}\n# Acceptance criteria\n{crit}\n"
            f"# Proposed implementation\n{proposal}\n")
