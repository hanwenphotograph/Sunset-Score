from __future__ import annotations

import json
import sys
from typing import Sequence

from .api import score_directories_independently, score_directory
from .arguments import build_parser
from .errors import SunsetScoreError
from .log import configure_logging, logger
from .results import IndependentScoreResult
from .termination import TerminationRequested, handle_termination_signals


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not arguments:
        parser.print_help()
        return 0

    args = parser.parse_args(arguments)
    if args.independently and not args.recursive:
        parser.error("--independently 只能与 -r/--recursive 一起使用")
    if args.directory is None:
        parser.print_help()
        return 0

    configure_logging()
    try:
        with handle_termination_signals():
            if args.independently:
                result = score_directories_independently(
                    args.directory,
                    interval=args.interval,
                    cpu_infer=args.cpu_infer,
                )
            else:
                result = score_directory(
                    args.directory,
                    recursive=args.recursive,
                    interval=args.interval,
                    cpu_infer=args.cpu_infer,
                )
    except SunsetScoreError as exc:
        logger.error("%s", exc)
        return 1
    except TerminationRequested as exc:
        logger.error("运行已收到终止信号：%s", exc.signal_name)
        return 128 + exc.signal_number
    except KeyboardInterrupt:
        logger.error("运行已由用户中断")
        return 130

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    elif isinstance(result, IndependentScoreResult):
        _print_independent_result(result)
    else:
        print(f"平均分: {result.average_score:.2f}")
        print(f"最高分: {result.max_score}")
    if isinstance(result, IndependentScoreResult) and result.failed_directory_count:
        return 1
    return 0


def _print_independent_result(result: IndependentScoreResult) -> None:
    print("独立目录分析结果:")
    for item in result.directories:
        if item.succeeded:
            print(
                f"- {item.directory}: 平均分 {item.average_score:.2f}，"
                f"最高分 {item.max_score}，采样 {item.sampled_count} 张"
            )
        else:
            print(f"- {item.directory}: 失败，{item.error}")
    print(f"分析报告: {result.report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
