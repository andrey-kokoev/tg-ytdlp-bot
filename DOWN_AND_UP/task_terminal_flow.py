from CONFIG.messages import safe_get_messages
from DOWN_AND_UP.runtime_task import RuntimeTask, with_terminal_outcome


def attach_and_render_terminal_outcome(
    *,
    user_id: int,
    outcome,
    task_context: RuntimeTask | None,
    formatter,
    rendered_text: str | None = None,
):
    if task_context is not None:
        task_context = with_terminal_outcome(task_context, outcome)
    text = rendered_text or formatter(safe_get_messages(user_id), outcome)
    return task_context, text
