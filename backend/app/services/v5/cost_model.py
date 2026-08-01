from decimal import Decimal

# Prices per 1M tokens in USD
LLM_PRICES = {
    "gpt-4o-mini": {
        "input": 0.150,
        "cached_input": 0.075,
        "output": 0.600,
    },
    "gpt-4o": {
        "input": 2.500,
        "cached_input": 1.250,
        "output": 10.000,
    },
    "gpt-4-turbo": {
        "input": 10.000,
        "cached_input": 5.000,
        "output": 30.000,
    },
    "gpt-4": {
        "input": 30.000,
        "cached_input": 15.000,
        "output": 60.000,
    },
    "gpt-3.5-turbo": {
        "input": 0.500,
        "cached_input": 0.250,
        "output": 1.500,
    },
    "text-embedding-3-small": {
        "input": 0.020,
        "cached_input": 0.020,
        "output": 0.0,
    },
    "text-embedding-3-large": {
        "input": 0.130,
        "cached_input": 0.130,
        "output": 0.0,
    },
    "text-embedding-ada-002": {
        "input": 0.100,
        "cached_input": 0.100,
        "output": 0.0,
    },
}


def estimate_cost(model: str | None, usage: dict) -> Decimal:
    """Estimate the cost of a model invocation given its usage stats."""
    if not model:
        return Decimal("0.0")

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    cached_tokens = usage.get("cached_tokens", 0) or 0

    # Normalize model name for lookup
    clean_model = model.split("/")[-1].lower()

    # Find matching price info
    price_info = None
    for pattern, prices in LLM_PRICES.items():
        if pattern in clean_model:
            price_info = prices
            break

    if not price_info:
        return Decimal("0.0")

    # Calculate uncached input vs cached input
    uncached_input = max(0, prompt_tokens - cached_tokens)

    input_cost = Decimal(str(uncached_input)) * Decimal(str(price_info["input"]))
    cached_cost = Decimal(str(cached_tokens)) * Decimal(str(price_info["cached_input"]))
    output_cost = Decimal(str(completion_tokens)) * Decimal(str(price_info["output"]))

    total_cost = (input_cost + cached_cost + output_cost) / Decimal("1000000")
    return total_cost
