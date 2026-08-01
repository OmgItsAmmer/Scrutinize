from pydantic import BaseModel, Field


class BudgetExceededError(Exception):
    """Exception raised when any run budget is exceeded."""

    def __init__(self, message: str):
        super().__init__(f"StopReason.budget_exceeded: {message}")


class RunBudget(BaseModel):
    # Generous fallback ceilings — real limits normally come from Settings
    # (run_budget_* in config.py) via BurrOrchestrator. These defaults only
    # apply if a caller constructs RunBudget without overrides.
    max_attempts: int = 10
    max_llm_calls: int = 50
    max_web_searches: int = 10
    max_tools: int = 10
    max_input_tokens: int = 200_000
    max_cost_usd: float = 10.0

    attempts: int = 0
    llm_calls: int = 0
    web_searches: int = 0
    tools: int = 0
    input_tokens: int = 0
    cost_usd: float = 0.0

    def check(self) -> None:
        """Check if any budget is exceeded. Raises BudgetExceededError if it is."""
        if self.attempts > self.max_attempts:
            raise BudgetExceededError(
                f"Attempts count ({self.attempts}) exceeded maximum allowed ({self.max_attempts})."
            )
        if self.llm_calls > self.max_llm_calls:
            raise BudgetExceededError(
                f"LLM calls count ({self.llm_calls}) exceeded maximum allowed ({self.max_llm_calls})."
            )
        if self.web_searches > self.max_web_searches:
            raise BudgetExceededError(
                f"Web search count ({self.web_searches}) exceeded maximum allowed ({self.max_web_searches})."
            )
        if self.tools > self.max_tools:
            raise BudgetExceededError(
                f"Tool execution count ({self.tools}) exceeded maximum allowed ({self.max_tools})."
            )
        if self.input_tokens > self.max_input_tokens:
            raise BudgetExceededError(
                f"Input tokens count ({self.input_tokens}) exceeded maximum allowed ({self.max_input_tokens})."
            )
        if self.cost_usd > self.max_cost_usd:
            raise BudgetExceededError(
                f"Cost budget ({self.cost_usd:.6f} USD) exceeded maximum allowed ({self.max_cost_usd:.6f} USD)."
            )
