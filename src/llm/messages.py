"""Build the messages of a call: stable prefix first, variable content last.

Providers cache the longest identical prefix of a prompt, so everything that never changes
between calls (instructions, examples) goes first and the one thing that changes (the posting)
goes last. In the spike, 99 % of a 3.2k-token prefix was served from cache on the second call.
"""

from src.llm.tasks import LLMTask

# (role, text), the shape ChatOpenAI accepts.
Message = tuple[str, str]


def wrap_untrusted(tag: str, text: str) -> str:
    """Fence untrusted text in `<tag>...</tag>` so the model treats it as data.

    A closing tag inside the text would let it escape the fence and pose as instructions, so
    any occurrence is neutralized first.
    """
    safe = text.replace(f"</{tag}", f"<\\/{tag}")
    return f"<{tag}>\n{safe}\n</{tag}>"


def build_messages(task: LLMTask, variable_input: str) -> list[Message]:
    messages: list[Message] = [("system", task.system_prompt)]
    for example_input, example_output in task.few_shots:
        messages.append(("user", wrap_untrusted(task.input_tag, example_input)))
        messages.append(("assistant", example_output))
    messages.append(("user", wrap_untrusted(task.input_tag, variable_input)))
    return messages
