import argparse
import functools
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Optional

from search import search


COLORS = (
    "\033[31m", "\033[32m", "\033[33m", "\033[34m",
    "\033[35m", "\033[36m", "\033[91m", "\033[92m",
)
RESET = "\033[0m"
SINGLE_LINE_LIMIT = 500


def timed(
    function: Callable[..., Any],
) -> Callable[..., Any]:
    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        report_time = kwargs.pop("_report_time", False)
        started = time.perf_counter()
        result = function(*args, **kwargs)
        if report_time:
            elapsed = time.perf_counter() - started
            print(
                "Search time: {:.6f} seconds".format(elapsed),
                file=sys.stderr,
            )
        return result
    return wrapper


@timed
def _run_search(
    text: str,
    patterns: list[str],
    case_sensitive: bool,
    method: str,
    count: Optional[int],
) -> Any:
    return search(text, patterns, case_sensitive, method, count)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search text with Aho–Corasick."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-s", "--string", help="source text")
    source.add_argument("-f", "--file", help="UTF-8 text file")
    parser.add_argument(
        "-p", "--pattern", action="append", required=True,
        help="pattern; repeat this option for multiple patterns",
    )
    cases = parser.add_mutually_exclusive_group()
    cases.add_argument(
        "-i", "--ignore-case", dest="case_sensitive",
        action="store_false",
        help="match without case sensitivity (default)",
    )
    cases.add_argument(
        "--case-sensitive", dest="case_sensitive",
        action="store_true", help="match exact character case",
    )
    parser.set_defaults(case_sensitive=False)
    parser.add_argument(
        "-m", "--method", choices=("first", "last"), default="first"
    )
    parser.add_argument(
        "-k", "--count", type=int,
        help="maximum occurrences per pattern",
    )
    color = parser.add_mutually_exclusive_group()
    color.add_argument("--color", dest="color", action="store_true")
    color.add_argument("--no-color", dest="color", action="store_false")
    parser.set_defaults(color=None)
    parser.add_argument(
        "--max-lines", type=int, default=10,
        help="maximum preview lines (default: 10)",
    )
    parser.add_argument(
        "--log-time", action="store_true",
        help="print search duration to stderr",
    )
    return parser


def _preview(
    text: str,
    results: dict[str, Optional[tuple[int, ...]]],
    patterns: list[str],
    use_color: bool,
    max_lines: int,
) -> str:
    limit = len(text)
    truncated = False
    newline_positions = [
        index for index, character in enumerate(text)
        if character == "\n"
    ]
    if len(newline_positions) >= max_lines:
        limit = newline_positions[max_lines - 1] + 1
        truncated = limit < len(text)
    elif not newline_positions and len(text) > SINGLE_LINE_LIMIT:
        limit = SINGLE_LINE_LIMIT
        truncated = True

    intervals: list[tuple[int, int, int]] = []
    for pattern_index, pattern in enumerate(patterns):
        matches = results.get(pattern)
        if matches:
            for start in matches:
                intervals.append(
                    (start, start + len(pattern), pattern_index)
                )

    char_colors: list[Optional[int]] = [None] * limit
    for start, end, pattern_index in sorted(intervals):
        for position in range(max(0, start), min(end, limit)):
            if char_colors[position] is None:
                char_colors[position] = pattern_index

    pieces: list[str] = []
    active: Optional[int] = None
    for position, character in enumerate(text[:limit]):
        color_index = char_colors[position] if use_color else None
        if active != color_index:
            if active is not None:
                pieces.append(RESET)
            if color_index is not None:
                pieces.append(COLORS[color_index % len(COLORS)])
            active = color_index
        pieces.append(character)

    if active is not None:
        pieces.append(RESET)
    if truncated:
        pieces.append("\n[preview truncated]")
    return "".join(pieces)


def main(argv: Optional[list[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if args.max_lines <= 0:
        parser.error("--max-lines must be a positive integer")
    if args.count is not None and args.count <= 0:
        parser.error("--count must be a positive integer")
    if any(not pattern for pattern in args.pattern):
        parser.error("patterns must not be empty")

    if args.file:
        path = Path(args.file)
        if not path.is_file():
            parser.error(
                "file does not exist or is not a regular file: "
                "{}".format(path)
            )
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            parser.error("cannot read UTF-8 file: {}".format(error))
    else:
        text = args.string

    use_color = (
        args.color if args.color is not None else sys.stdout.isatty()
    )
    use_color = use_color and "NO_COLOR" not in os.environ

    try:
        results = _run_search(
            text, args.pattern, args.case_sensitive, args.method,
            args.count, _report_time=args.log_time,
        )
    except (TypeError, ValueError) as error:
        parser.error(str(error))

    print("Source preview:")
    print(
        _preview(
            text, results or {}, args.pattern, use_color, args.max_lines
        )
    )
    print("Results (zero-based character offsets):")
    for pattern in dict.fromkeys(args.pattern):
        result = results.get(pattern) if results else None
        print("{}: {}".format(pattern, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
