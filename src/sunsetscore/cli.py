from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Sequence

from .api import score_directories_independently, score_directory
from .arguments import build_parser
from .autopack.packer import (
    AutopackResult,
    pack_independent_result,
    pack_score_result,
)
from .errors import SunsetScoreError
from .log import configure_logging, logger
from .results import IndependentScoreResult, ScoreResult, SunsetRange
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
    if args.cpu_infer and (
        args.gpu_workers is not None or args.gpu_memory_limit is not None
    ):
        parser.error("--cpu-infer 不能与 GPU 限制参数一起使用")

    configure_logging()
    try:
        with handle_termination_signals():
            if args.independently:
                result = score_directories_independently(
                    args.directory,
                    interval=args.interval,
                    cpu_infer=args.cpu_infer,
                    gpu_workers=args.gpu_workers,
                    gpu_memory_limit=args.gpu_memory_limit,
                    force=args.force,
                )
            else:
                result = score_directory(
                    args.directory,
                    recursive=args.recursive,
                    interval=args.interval,
                    cpu_infer=args.cpu_infer,
                    gpu_workers=args.gpu_workers,
                    gpu_memory_limit=args.gpu_memory_limit,
                    force=args.force,
                )
            packed = (
                _pack_result(args.directory, result, recursive=args.recursive)
                if args.autopack
                else None
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
        print(f"检测到晚霞: {_yes_no(result.has_sunset)}")
        print(f"晚霞区间: {_format_ranges(result.sunset_ranges)}")
    if packed is not None and not args.json:
        print(f"晚霞打包目录: {packed.output_directory}")
        print(
            f"已打包照片: {packed.photo_count} 张，"
            f"来源目录: {packed.source_directory_count} 个"
        )
    if isinstance(result, IndependentScoreResult) and result.failed_directory_count:
        return 1
    return 0


def _print_independent_result(result: IndependentScoreResult) -> None:
    print("独立目录分析结果:")
    for item in result.directories:
        if item.succeeded:
            print(
                f"- {item.directory}: 平均分 {item.average_score:.2f}，"
                f"最高分 {item.max_score}，晚霞 {_yes_no(bool(item.has_sunset))}，"
                f"区间 {_format_ranges(item.sunset_ranges)}，"
                f"采样 {item.sampled_count} 张"
            )
        else:
            print(f"- {item.directory}: 失败，{item.error}")
    print(f"分析报告: {result.report_path}")


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _format_ranges(ranges: Sequence[SunsetRange]) -> str:
    if not ranges:
        return "-"
    return "；".join(
        item.start_photo
        if item.start_photo == item.end_photo
        else f"{item.start_photo} 至 {item.end_photo}"
        for item in ranges
    )


def _pack_result(
    directory: Path,
    result: ScoreResult | IndependentScoreResult,
    *,
    recursive: bool,
) -> AutopackResult:
    if isinstance(result, IndependentScoreResult):
        return pack_independent_result(directory, result)
    return pack_score_result(directory, result, recursive=recursive)


if __name__ == "__main__":
    raise SystemExit(main())
