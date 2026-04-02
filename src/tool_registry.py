from google.genai import types

class ToolRegistry:
    """Map tool declarations to Python callables for Gemini tool use.

    Attributes:
        _tools: Mapping of tool names to Python callables.
        _declarations: Gemini function declarations registered for the tools.

    """
    def __init__(self):
        """Initialize empty tool declaration and callable registries.

        Returns:
            None

        """
        self._tools = {}
        self._declarations: list[types.FunctionDeclaration] = []

    def register(self, func, declaration: types.FunctionDeclaration):
        """Register a function with its LLM-facing declaration.

        Args:
            func: Python callable that implements the tool.
            declaration: Gemini function declaration exposed to the LLM.

        Returns:
            None

        """
        self._tools[declaration.name] = func
        self._declarations.append(declaration)

    def execute(self, tool_name: str, **kwargs):
        """Execute a registered tool by name and return the result.

        Args:
            tool_name: Name of the tool to execute.
            **kwargs: Keyword arguments forwarded to the tool.

        Returns:
            dict: Tool result payload or error payload.

        """
        if tool_name not in self._tools:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = self._tools[tool_name](**kwargs)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def get_tools_for_api(self) -> types.Tool:
        """Return tool declarations formatted for the Gemini API.

        Returns:
            types.Tool: Gemini tool wrapper containing all registered
            declarations.

        """
        return types.Tool(function_declarations=self._declarations)

    def list_tools(self):
        """Print available tool names and descriptions.

        Returns:
            None

        """
        for dec in self._declarations:
            print(f"Tool Name: {dec.name}, Description: {dec.description}")

