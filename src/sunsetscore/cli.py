from __future__ import annotations

import json
import sys
from typing import Sequence

from .api import score_directory
from .arguments import build_parser
from .errors import SunsetScoreError
from .log import configure_logging, logger


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not arguments:
        parser.print_help()
        return 0

    args = parser.parse_args(arguments)
    if args.directory is None:
        parser.print_help()
        return 0

    configure_logging()
    try:
        result = score_directory(
            args.directory,
            recursive=args.recursive,
            interval=args.interval,
        )
    except SunsetScoreError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.error("运行已由用户中断")
        return 130

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"平均分: {result.average_score:.2f}")
        print(f"最高分: {result.max_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
