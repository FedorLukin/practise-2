from collections import deque
from typing import Optional, Union


class _Node:
    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.failure: Optional[_Node] = None
        self.outputs: list[str] = []


def _fold_character(character: str) -> str:
    folded = character.casefold()
    return folded if len(folded) == 1 else character


def _build_automaton(patterns: list[str]) -> _Node:
    root = _Node()
    root.failure = root

    for pattern in patterns:
        state = root
        for character in pattern:
            state = state.children.setdefault(character, _Node())
        if pattern not in state.outputs:
            state.outputs.append(pattern)

    queue: deque[_Node] = deque()
    for child in root.children.values():
        child.failure = root
        queue.append(child)

    while queue:
        state = queue.popleft()
        for character, child in state.children.items():
            fallback = state.failure
            while fallback is not root and character not in fallback.children:
                fallback = fallback.failure

            child.failure = fallback.children.get(character, root)
            for pattern in child.failure.outputs:
                if pattern not in child.outputs:
                    child.outputs.append(pattern)
            queue.append(child)

    return root


def search(
    string: str,
    sub_string: Union[str, list[str], tuple[str, ...]],
    case_sensitivity: bool = False,
    method: str = "first",
    count: Optional[int] = None,
) -> Union[Optional[tuple[int, ...]], dict[str, Optional[tuple[int, ...]]]]:
    if not isinstance(string, str):
        raise TypeError("string must be a string")
    if method not in ("first", "last"):
        raise ValueError("method must be 'first' or 'last'")
    if count is not None and (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count <= 0
    ):
        raise ValueError("count must be a positive integer or None")

    collection = isinstance(sub_string, (list, tuple))
    patterns = list(sub_string) if collection else [sub_string]

    if any(not isinstance(pattern, str) for pattern in patterns):
        raise TypeError("patterns must be strings")
    if any(not pattern for pattern in patterns):
        raise ValueError("empty patterns are not supported")
    if not string:
        return None

    original_patterns = list(dict.fromkeys(patterns))

    if case_sensitivity:
        normalized_patterns = {
            pattern: pattern for pattern in original_patterns
        }
        normalized_text = string
    else:
        normalized_patterns = {
            pattern: "".join(
                _fold_character(character) for character in pattern
            )
            for pattern in original_patterns
        }
        normalized_text = "".join(
            _fold_character(character) for character in string
        )

    normalized_to_original: dict[str, list[str]] = {}
    for original, normalized in normalized_patterns.items():
        normalized_to_original.setdefault(normalized, []).append(original)

    root = _build_automaton(list(normalized_to_original))
    found: dict[str, list[int]] = {
        pattern: [] for pattern in original_patterns
    }
    events: list[tuple[str, int]] = []
    state = root

    for index, character in enumerate(normalized_text):
        while state is not root and character not in state.children:
            state = state.failure
        state = state.children.get(character, root)

        for normalized in state.outputs:
            start = index - len(normalized) + 1
            for original in normalized_to_original[normalized]:
                events.append((original, start))

    if collection and count is not None:
        if method == "first":
            events = events[:count]
        else:
            events = events[-count:]

    for pattern, start in events:
        found[pattern].append(start)

    results: dict[str, Optional[tuple[int, ...]]] = {}
    for pattern in original_patterns:
        occurrences = found[pattern]
        if method == "last":
            occurrences.reverse()
        if count is not None and not collection:
            occurrences = occurrences[:count]
        results[pattern] = tuple(occurrences) if occurrences else None

    if collection:
        return {pattern: results[pattern] for pattern in patterns}

    return results[patterns[0]]
