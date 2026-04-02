from google.genai import types
from src.gemini_client import GeminiClient
from src.tool_registry import ToolRegistry
from src.prompts import DQ_AGENT_TOOL_PROMPT


class DQToolAgent:
    """Run a Gemini-driven tool loop for data quality investigations.

    Attributes:
        gemini_client: Gemini client used to generate tool-calling responses.
        tool_registry: Registry of callable tools available to the agent.

    """
    def __init__(self, gemini_client: GeminiClient, tool_registry: ToolRegistry):
        """Store the Gemini client and callable tool registry.

        Args:
            gemini_client: Gemini client used to drive the agent loop.
            tool_registry: Registry of callable tools exposed to the model.

        """
        self.gemini_client = gemini_client
        self.tool_registry = tool_registry

    def run(self, user_message: str) -> str:
        """Process a user request by iteratively invoking tools and the model.

        Args:
            user_message: User request to process.

        Returns:
            str: Final agent response after the tool-calling loop completes.

        """

        messages = [
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)]
            )
        ]

        for iteration in range(10):
            # Send to LLM with available tools
            response = self.gemini_client.client.models.generate_content(
                model=self.gemini_client.model,
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=DQ_AGENT_TOOL_PROMPT,
                    tools=[self.tool_registry.get_tools_for_api()]
                )
            )

            candidate = response.candidates[0]

            # Check if LLM wants to call a tool
            has_function_call = candidate.content.parts and any(
                hasattr(part, "function_call") and part.function_call
                for part in candidate.content.parts
            )

            if not has_function_call:
                # LLM is done — return final text response
                return response.text

            # LLM requested tool calls — execute them
            tool_results = []
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    func_call = part.function_call
                    tool_name = func_call.name
                    tool_args = dict(func_call.args)

                    # call the execute method of tool registry which execute the actual Python function
                    print(f"\n→ Calling tool: {tool_name}({tool_args})")
                    result = self.tool_registry.execute(tool_name,**tool_args)
                    print(f"Result: {result}")
                    tool_results.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": result}
                            )
                        )
                    )

            # Send LLM response and tool results back to LLM, and continue the loop
            messages.append(candidate.content)
            messages.append(types.Content(role="tool", parts=tool_results))

        return "Max iterations reached"

