"""No truncation: split on line boundaries when possible, otherwise Unicode characters."""

from app.infra.metrics import conservative_tokens


def chunks(text: str, token_budget: int) -> list[str]:
    result: list[str] = []
    start = 0
    while start < len(text):
        size = 0
        end = start
        while end < len(text):
            width = conservative_tokens(text[end])
            if size + width > token_budget:
                break
            size += width
            end += 1
        if end == len(text):
            result.append(text[start:end])
            break
        newline = text.rfind("\n", start, end)
        if newline > start:
            end = newline + 1
        if end == start:
            end += 1
        result.append(text[start:end])
        start = end
    return result
