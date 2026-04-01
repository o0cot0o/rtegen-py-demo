#!/usr/bin/env python3
"""
TOPPERS/A-RTEGEN Python Demo — 入口

这是一个 Python 简化版的 AUTOSAR RTE 代码生成器 Demo，
对应 Java 项目中的 CLI 入口 (RteGeneratorApp)。

流水线:
  ARXML 文件 → [解析器] → 中间模型 → [代码生成器] → C 源文件

用法:
  python main.py <arxml文件> [<arxml文件2> ...] [-o <输出目录>]

示例:
  python main.py sample.arxml -o output
"""

import argparse
import sys
import os

from arxml_parser import ArxmlParser
from code_generator import CodeGenerator, print_connector_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A-RTEGEN Python Demo: ARXML → RTE C Code Generator",
    )
    parser.add_argument(
        "arxml_files",
        nargs="+",
        metavar="ARXML",
        help="Input ARXML file(s)",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: output)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 检查输入文件是否存在
    for f in args.arxml_files:
        if not os.path.isfile(f):
            print(f"Error: file not found: {f}", file=sys.stderr)
            sys.exit(1)

    print("=" * 60)
    print("  TOPPERS/A-RTEGEN Python Demo")
    print("  Automotive Runtime Environment Generator")
    print("=" * 60)

    # 阶段 1: 解析 ARXML → 中间模型
    print(f"\n[1/2] Parsing {len(args.arxml_files)} ARXML file(s)...")
    parser = ArxmlParser()
    module = parser.parse(*args.arxml_files)

    print(f"  Base types:    {len(module.base_types)}")
    print(f"  Data types:    {len(module.data_types)}")
    print(f"  Components:    {len(module.components)}")
    print(f"  Connectors:    {len(module.connectors)}")

    # 打印模型摘要
    for comp in module.components:
        print(f"\n  SWC: {comp.name}")
        for port in comp.ports:
            print(f"    {port.port_kind:6s} {port.name}"
                  f"  iface={port.interface_name}"
                  f"  elem={port.data_element}"
                  f"  type={port.data_type}")
        for run in comp.runnables:
            evt_info = f"  events={run.events}" if run.events else ""
            print(f"    Runnable: {run.name}  period={run.min_interval}s{evt_info}")

    print_connector_report(module)

    # 阶段 2: 生成 C 代码
    print("[2/2] Generating C source files...")
    generator = CodeGenerator(module, output_dir=args.output)
    generator.generate()

    # 列出生成的文件
    print("Output files:")
    for f in sorted(os.listdir(args.output)):
        size = os.path.getsize(os.path.join(args.output, f))
        print(f"  {f:30s}  {size:6d} bytes")

    print("\nDone. Use 'gcc -c output/*.c' to verify compilation.")


if __name__ == "__main__":
    main()
