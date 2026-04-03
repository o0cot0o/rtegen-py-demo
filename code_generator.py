"""
C 代码生成层 (Code Generator)

对应 Java 项目中 codegen 模块的功能:
  将中间模型 (RteModule) 转换为 AUTOSAR RTE C 语言源文件。

生成的文件:
  - Rte.h             — RTE 总头文件
  - Rte_Type.h        — RTE 类型定义
  - Rte_Application.h — 应用 API 头文件
  - Rte_<Swc>.h       — SWC 专用头文件
  - Rte_<Swc>.c       — SWC 实现源文件
"""

import os
from intermediate_model import RteModule, SoftwareComponent, Port


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _header_guard(filename: str) -> str:
    """生成 C 头文件 include guard 宏名"""
    return filename.upper().replace(".", "_").replace("-", "_") + "_"


def _write_file(output_dir: str, filename: str, content: str):
    """写入文件到输出目录"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Generated: {filename}")


def _c_comment(text: str, style: str = "block") -> str:
    """生成 C 注释"""
    if style == "line":
        return f"/* {text} */"
    return f"/*\n * {text}\n */"


# ──────────────────────────────────────────────
# 代码生成器
# ──────────────────────────────────────────────

class CodeGenerator:
    """
    RTE C 代码生成器

    对应 Java 项目中 RteCodeGenerator + Acceleo 模板的功能，
    但使用 Python 字符串模板替代 MTL 模板。
    """

    def __init__(self, module: RteModule, output_dir: str = "output"):
        self.module = module
        self.output_dir = output_dir

    def generate(self):
        """生成所有 RTE 文件"""
        print(f"\nGenerating RTE files to: {self.output_dir}")
        self._gen_rte_h()
        self._gen_rte_type_h()
        self._gen_rte_application_h()
        for comp in self.module.components:
            self._gen_rte_swc_h(comp)
            self._gen_rte_swc_c(comp)
        print("Generation complete.\n")

    # ─── Rte.h ────────────────────────────────

    def _gen_rte_h(self):
        guard = _header_guard("Rte.h")
        includes = []
        for comp in self.module.components:
            includes.append(f'#include "Rte_{comp.name}.h"')

        lines = [
            _c_comment("TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE header"),
            "",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include \"Rte_Type.h\"",
            "",
        ]
        lines.extend(includes)
        lines.extend([
            "",
            f"#endif /* {guard} */",
        ])
        _write_file(self.output_dir, "Rte.h", "\n".join(lines) + "\n")

    # ─── Rte_Type.h ───────────────────────────

    def _gen_rte_type_h(self):
        guard = _header_guard("Rte_Type.h")
        lines = [
            _c_comment("TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE type definitions"),
            "",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            "#include <stdint.h>",
            "",
        ]

        # 基础类型 typedef
        if self.module.base_types:
            lines.append("/* Base types */")
            for bt in self.module.base_types:
                lines.append(f"typedef {bt.native_declaration} {bt.name};")
            lines.append("")

        # 数据类型 typedef
        if self.module.data_types:
            lines.append("/* Application data types */")
            for dt in self.module.data_types:
                lines.append(f"typedef {dt.base_type} {dt.name};")
            lines.append("")

        lines.append(f"#endif /* {guard} */")
        _write_file(self.output_dir, "Rte_Type.h", "\n".join(lines) + "\n")

    # ─── Rte_Application.h ────────────────────

    def _gen_rte_application_h(self):
        guard = _header_guard("Rte_Application.h")
        lines = [
            _c_comment("TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE application API"),
            "",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            '#include "Rte_Type.h"',
            "",
        ]

        for comp in self.module.components:
            lines.append(f"/* === {comp.name} === */")
            for port in comp.ports:
                if port.port_kind == "P-PORT" and port.data_type:
                    lines.append(f"#define Rte_WriteAAA_{comp.name}_{port.name}_{port.data_element}(data) \\")
                    lines.append(f"    Rte_Write_{comp.name}_{port.name}_{port.data_element}_Impl(data)")
                    lines.append("")
                elif port.port_kind == "R-PORT" and port.data_type:
                    lines.append(f"#define Rte_Read_{comp.name}_{port.name}_{port.data_element}(data) \\")
                    lines.append(f"    Rte_Read_{comp.name}_{port.name}_{port.data_element}_Impl(data)")
                    lines.append("")

        lines.append(f"#endif /* {guard} */")
        _write_file(self.output_dir, "Rte_Application.h", "\n".join(lines) + "\n")

    # ─── Rte_<Swc>.h ──────────────────────────

    def _gen_rte_swc_h(self, comp: SoftwareComponent):
        filename = f"Rte_{comp.name}.h"
        guard = _header_guard(filename)

        lines = [
            _c_comment(f"TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE header for {comp.name}"),
            "",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            '#include "Rte_Type.h"',
            "",
        ]

        # 函数声明
        for port in comp.ports:
            if port.port_kind == "P-PORT" and port.data_type:
                func_name = f"Rte_Write_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type} data);")
            elif port.port_kind == "R-PORT" and port.data_type:
                func_name = f"Rte_Read_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type}* data);")

        lines.append("")

        # Runnable 声明
        for run in comp.runnables:
            lines.append(f"void {run.name}(void);")

        lines.extend([
            "",
            f"#endif /* {guard} */",
        ])
        _write_file(self.output_dir, filename, "\n".join(lines) + "\n")

    # ─── Rte_<Swc>.c ──────────────────────────

    def _gen_rte_swc_c(self, comp: SoftwareComponent):
        filename = f"Rte_{comp.name}.c"

        lines = [
            _c_comment(f"TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE implementation for {comp.name}"),
            "",
            f'#include "Rte_{comp.name}.h"',
            "",
        ]

        # 模块级静态缓冲区
        lines.append("/* Data buffers */")
        for port in comp.ports:
            if port.data_type and port.data_element:
                lines.append(f"static {port.data_type} {port.name}_buffer;")
        lines.append("")

        # Write 函数实现
        for port in comp.ports:
            if port.port_kind == "P-PORT" and port.data_type:
                func_name = f"Rte_Write_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type} data)")
                lines.append("{")
                lines.append(f"    {port.name}_buffer = data;")
                lines.append("    return E_OK;")
                lines.append("}")
                lines.append("")

        # Read 函数实现
        for port in comp.ports:
            if port.port_kind == "R-PORT" and port.data_type:
                func_name = f"Rte_Read_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type}* data)")
                lines.append("{")
                lines.append("    if (data == NULL_PTR)")
                lines.append("    {")
                lines.append("        return E_NOT_OK;")
                lines.append("    }")
                lines.append(f"    *data = {port.name}_buffer;")
                lines.append("    return E_OK;")
                lines.append("}")
                lines.append("")

        # Runnable 实现
        for run in comp.runnables:
            comment_parts = [f"Runnable: {run.name}"]
            if run.min_interval > 0:
                comment_parts.append(f"Period: {run.min_interval}s")
            if run.events:
                comment_parts.append(f"Events: {', '.join(run.events)}")

            lines.append(_c_comment("\n * ".join(comment_parts)))
            lines.append(f"void {run.name}(void)")
            lines.append("{")
            lines.append("    /* User implementation */")
            lines.append("}")
            lines.append("")

        _write_file(self.output_dir, filename, "\n".join(lines) + "\n")


# ──────────────────────────────────────────────
# 连接器分析报告
# ──────────────────────────────────────────────

def print_connector_report(module: RteModule):
    """打印连接器关系报告（对应 Composition SWC 的连接信息）"""
    if not module.connectors:
        return

    print("Assembly Connectors:")
    print("-" * 60)
    for conn in module.connectors:
        print(f"  {conn.name}")
        print(f"    Provider:  {conn.provider_swc}.{conn.provider_port}")
        print(f"    Requester: {conn.requester_swc}.{conn.requester_port}")
    print()
