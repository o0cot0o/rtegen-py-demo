      
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
        # 构建连接器映射: (provider_swc, provider_port) -> [Connector, ...]
        self._connector_map: dict[tuple[str, str], list] = {}
        for conn in module.connectors:
            key = (conn.provider_swc, conn.provider_port)
            self._connector_map.setdefault(key, []).append(conn)

    def generate(self):
        """生成所有 RTE 文件"""
        print(f"\nGenerating RTE files to: {self.output_dir}")
        self._gen_rte_h()
        self._gen_rte_type_h()
        self._gen_rte_cbk_h()
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
            "#include \"Rte_Cbk.h\"",
            "",
        ]
        lines.extend(includes)
        lines.extend([
            "",
            f"#endif /* {guard} */",
        ])
        _write_file(self.output_dir, "Rte.h", "\n".join(lines) + "\n")

    # ─── Rte_Cbk.h ──────────────────────────

    def _gen_rte_cbk_h(self):
        """生成回调声明头文件，包含连接器相关的回调"""
        guard = _header_guard("Rte_Cbk.h")
        lines = [
            _c_comment("TOPPERS/A-RTEGEN Python Demo\n * Auto-generated RTE callback declarations"),
            "",
            f"#ifndef {guard}",
            f"#define {guard}",
            "",
            '#include "Rte_Type.h"',
            "",
        ]

        if self.module.connectors:
            lines.append("/* Callbacks for inter-SWC data routing */")
            for conn in self.module.connectors:
                cbk_name = f"Rte_Cbk_{conn.requester_swc}_{conn.requester_port}"
                lines.append(f"void {cbk_name}(void);")
            lines.append("")
        else:
            lines.append("/* No connectors defined — no callbacks required */")
            lines.append("")

        lines.append(f"#endif /* {guard} */")
        _write_file(self.output_dir, "Rte_Cbk.h", "\n".join(lines) + "\n")

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
            "#include <stdbool.h>",
            "",
        ]

        # AUTOSAR 标准类型
        lines.append("/* AUTOSAR standard types */")
        lines.extend([
            "typedef unsigned char  uint8;",
            "typedef unsigned short uint16;",
            "typedef unsigned int   uint32;",
            "typedef signed char    sint8;",
            "typedef signed short   sint16;",
            "typedef signed int     sint32;",
            "typedef float          float32;",
            "typedef double         float64;",
            "typedef uint8          Std_ReturnType;",
            "",
        ])

        # 标准宏定义
        lines.append("/* AUTOSAR standard macros */")
        lines.extend([
            "#define E_OK      0x00U",
            "#define E_NOT_OK  0x01U",
            "#define NULL_PTR  ((void *)0)",
            "",
        ])

        # 基础类型 typedef (ARXML 自定义，跳过与标准类型重名的)
        standard_types = {"uint8", "uint16", "uint32", "sint8", "sint16", "sint32", "float32", "float64", "Std_ReturnType"}
        custom_types = [bt for bt in self.module.base_types if bt.name not in standard_types]
        if custom_types:
            lines.append("/* Custom base types from ARXML */")
            for bt in custom_types:
                lines.append(f"typedef {bt.native_declaration} {bt.name};")
            lines.append("")

        # 数据类型 typedef (跳过自引用: typedef uint16 uint16;)
        unique_data_types = [dt for dt in self.module.data_types if dt.name != dt.base_type]
        if unique_data_types:
            lines.append("/* Application data types */")
            for dt in unique_data_types:
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
                    lines.append(f"#define Rte_Write_{comp.name}_{port.name}_{port.data_element}(data) \\")
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

        # 函数声明 — Write (P-PORT)
        lines.append("/* Write API (P-PORT) */")
        for port in comp.ports:
            if port.port_kind == "P-PORT" and port.data_type:
                func_name = f"Rte_Write_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type} data);")
        lines.append("")

        # 函数声明 — Read (R-PORT)
        lines.append("/* Read API (R-PORT) */")
        for port in comp.ports:
            if port.port_kind == "R-PORT" and port.data_type:
                func_name = f"Rte_Read_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type}* data);")
        lines.append("")

        # 调度相关声明
        has_timing = any(run.min_interval > 0 for run in comp.runnables)
        if has_timing:
            lines.append("/* Scheduler API */")
            for run in comp.runnables:
                if run.min_interval > 0:
                    lines.append(f"Std_ReturnType Rte_IsRunnableReady_{run.name}(void);")
            lines.append(f"void Rte_Task_{comp.name}(void);")
            lines.append("")

        # Runnable 声明
        lines.append("/* Runnable declarations */")
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

        # ─── 数据缓冲区 ───
        lines.append("/* Data buffers */")
        for port in comp.ports:
            if port.data_type and port.data_element:
                lines.append(f"static {port.data_type} {port.name}_buffer;")
        lines.append("")

        # ─── Write 函数实现 (P-PORT) ───
        for port in comp.ports:
            if port.port_kind == "P-PORT" and port.data_type:
                func_name = f"Rte_Write_{comp.name}_{port.name}_{port.data_element}"
                lines.append(f"Std_ReturnType {func_name}_Impl({port.data_type} data)")
                lines.append("{")
                lines.append(f"    {port.name}_buffer = data;")

                # 连接器: 将数据路由到连接的 R-PORT
                conn_key = (comp.name, port.name)
                if conn_key in self._connector_map:
                    for conn in self._connector_map[conn_key]:
                        lines.append(f"    /* Connector: {conn.provider_swc}.{conn.provider_port} -> {conn.requester_swc}.{conn.requester_port} */")
                        lines.append(f"    {conn.requester_port}_buffer = data; /* cross-component routing */")

                lines.append("    return E_OK;")
                lines.append("}")
                lines.append("")

        # ─── Read 函数实现 (R-PORT) ───
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

        # ─── 调度器实现 ───
        timing_runnables = [r for r in comp.runnables if r.min_interval > 0]
        if timing_runnables:
            lines.append("/* Scheduler */")

            # 周期计数器
            for run in timing_runnables:
                lines.append(f"static uint32 Rte_Counter_{run.name} = 0U;")
            lines.append("")

            # 就绪检查函数
            for run in timing_runnables:
                tick_count = int(run.min_interval * 1000)  # 假设 tick=1ms
                lines.append(f"Std_ReturnType Rte_IsRunnableReady_{run.name}(void)")
                lines.append("{")
                lines.append(f"    Rte_Counter_{run.name}++;")
                lines.append(f"    if (Rte_Counter_{run.name} >= {tick_count}U) /* period={run.min_interval}s */")
                lines.append("    {")
                lines.append(f"        Rte_Counter_{run.name} = 0U;")
                lines.append("        return E_OK;")
                lines.append("    }")
                lines.append("    return E_NOT_OK;")
                lines.append("}")
                lines.append("")

            # 任务入口函数
            lines.append(f"void Rte_Task_{comp.name}(void)")
            lines.append("{")
            for run in timing_runnables:
                lines.append(f"    if (E_OK == Rte_IsRunnableReady_{run.name}())")
                lines.append("    {")
                lines.append(f"        {run.name}();")
                lines.append("    }")
            lines.append("}")
            lines.append("")

        # ─── Runnable 实现 ───
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
