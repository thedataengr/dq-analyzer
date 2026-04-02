from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """Define the abstract interface shared by LLM client implementations."""
    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the backing LLM service is ready to accept requests.

        Returns:
            bool: True if the service is available; otherwise, False.

        """
        ...

    @abstractmethod
    def chat(self, system_prompt: str, user_message: str) -> str | None:
        """Send a chat request and return the model's text response.

        Args:
            system_prompt: System instructions for the model.
            user_message: User prompt content to submit.

        Returns:
            str | None: Generated response text, or `None` on failure.

        """
        ...

    @abstractmethod
    def analyse_table(self, table_name: str, null_stats: dict, row_count: int) -> dict | None:
        """Return structured analysis for the supplied table statistics.

        Args:
            table_name: Name of the table being analyzed.
            null_stats: Null counts grouped by column.
            row_count: Total number of rows in the table.

        Returns:
            dict | None: Structured analysis output, or `None` on failure.

        """
        ...
