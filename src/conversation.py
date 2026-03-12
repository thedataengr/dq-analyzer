import json

class ConversationHistory:
    def __init__(self, system_prompt: str, max_history: int=20):
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.context_messages = []   # never truncated
        self.messages = []           # sliding window applied for messages

    def add_user_message(self, content: str):
        self.messages.append(
            {
                "role": "user",
                "content": content
            }
        )

    def add_assistant_message(self, content: str):
        self.messages.append(
            {
                "role": "assistant",
                "content": content
            }
        )

    def inject_context(self, data: dict, label: str):
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
        self.messages = []

    @property
    def message_count(self):
        return len(self.messages)
