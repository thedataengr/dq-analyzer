import json

class ConversationHistory:
    """Track system, context, and chat messages for LLM conversations.

    Attributes:
        system_prompt: System instruction used for the conversation.
        max_history: Maximum number of interactive messages to retain.
        context_messages: Persisted context messages that are never truncated.
        messages: Sliding window of interactive conversation messages.

    """
    def __init__(self, system_prompt: str, max_history: int=20):
        """Initialize conversation state with a bounded chat history window.

        Args:
            system_prompt: System prompt sent with every API call.
            max_history: Maximum number of interactive messages to retain.

        """
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.context_messages = []   # never truncated
        self.messages = []           # sliding window applied for messages

    def add_user_message(self, content: str):
        """Append a user-authored message to the conversation history.

        Args:
            content: User message text.

        Returns:
            None

        """
        self.messages.append(
            {
                "role": "user",
                "content": content
            }
        )

    def add_assistant_message(self, content: str):
        """Append an LLM message to the conversation history.

        Args:
            content: LLM message text.

        Returns:
            None

        """
        self.messages.append(
            {
                "role": "assistant",
                "content": content
            }
        )

    def inject_context(self, data: dict, label: str):
        """Insert structured context messages that persist across turns.

        Args:
            data: Structured context payload to inject.
            label: Human-readable label describing the context.

        Returns:
            None

        """
        context_message = f"""
        [CONTEXT: {label}]
        {json.dumps(data, default=str, indent=2)}
        [END CONTEXT]
        """
        self.context_messages.append({
            "role": "user",
            "content": context_message
        })
        self.context_messages.append({
            "role": "assistant",
            "content": f"I have received and noted the {label} context."
        })

    def get_messages_for_api(self) -> list[dict]:
        """Build the message payload sent to the LLM API.

        Returns:
            list[dict]: Message list containing the system prompt, persistent
            context, and recent interactive history.

        """
        return (
            [
                {
                    "role": "system",
                    "content": self.system_prompt
                }
            ]
            + self.context_messages
            + self.messages[-self.max_history:]
        )

    def clear(self):
        """Clear the sliding window of interactive chat messages.

        Returns:
            None

        """
        self.messages = []

    @property
    def message_count(self):
        """Return the number of interactive chat messages currently stored.

        Returns:
            int: Number of stored interactive messages.

        """
        return len(self.messages)
