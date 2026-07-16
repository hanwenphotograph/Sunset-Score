from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "用法:", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法:", 1)

    def error(self, message: str) -> None:
        translations = {
            "unrecognized arguments:": "无法识别的参数:",
            "the following arguments are required:": "缺少必要参数:",
        }
        for source, target in translations.items():
            message = message.replace(source, target)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: 错误: {message}\n")


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("必须大于等于 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(
        prog="sunsetscore",
        description="采样输入目录中的照片，并使用本地视觉语言模型计算晚霞指数。",
        add_help=False,
    )
    parser._positionals.title = "位置参数"
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助信息并退出。")
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        help="包含 JPG 或 PNG 照片的输入目录。",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="递归扫描输入目录，但不跟随符号链接。",
    )
    parser.add_argument(
        "-ind",
        "--independently",
        action="store_true",
        help="与递归扫描配合，将每个合法子目录分别分析并生成 Markdown 报告。",
    )
    parser.add_argument(
        "--interval",
        type=positive_int,
        help="采样间隔，覆盖本地配置中的值，默认值为 10。",
    )
    parser.add_argument(
        "--cpu-infer",
        action="store_true",
        help="强制使用 CPU 推理，跳过 GPU 探测与加速。",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="仅在标准输出中打印 JSON 结论。",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="显示版本号并退出。",
    )
    return parser
