from src.conversation import ConversationHistory
from src.prompts import DQ_SYSTEM_PROMPT
from src.db_inspector import DBInspector
from src.models import TableProfile
from src.reporter import DQReporter
from src.llm_client import LLMClient

class DQChatSession:
    def __init__(self, llm_client: LLMClient, inspector: DBInspector, reporter: DQReporter):
        self.llm_client = llm_client
        self.inspector = inspector
        self.reporter = reporter

    def start(self, profiles: list[TableProfile]):
        table_names = [p.name for p in profiles]
        print("=" * 60)
        print("DQ CHAT SESSION")
        print("=" * 60)
        print(f"I have analysed {len(profiles)} tables in your database.")
        print(f"Tables available: {', '.join(table_names)}. You can ask me questions about them.")
        print("Type 'exit' or 'quit' to end the session.")
        print("=" * 60 + "\n")

        history = ConversationHistory(DQ_SYSTEM_PROMPT)
        table_details = []
        for profile in profiles:
            table_details.append(
                {
                    "table_name": profile.name,
                    "table_schema": self.inspector.get_table_schema(profile.name),
                    "row_count": profile.row_count,
                    "null_pct": profile.null_pct,
                    "column_count": profile.column_count,
                    "status": profile.get_status(),
                    "null_counts": self.inspector.get_null_counts(profile.name)
                }
            )
        context = {
            "table_details": table_details,
        }

        history.inject_context(context, "Data Quality Analysis")

        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ("exit","quit"):
                print("Session ended.")
                break

            history.add_user_message(user_input)

            response = self.llm_client.chat_with_history(
                history.get_messages_for_api()
            )

            if response:
                history.add_assistant_message(response)
                print(f"\nAgent: {response}\n")
            else:
                print("Agent: Sorry, I couldn't process that request.\n")

