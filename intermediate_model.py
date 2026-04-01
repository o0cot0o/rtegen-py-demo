"""
中间模型层 (Intermediate Model)

对应 Java 项目中 m2m 模块生成的 RTE Module 模型。
该模型是 AUTOSAR 领域模型到 C 代码之间的桥梁，
包含了代码生成所需的所有结构化信息。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BaseType:
    """C 语言基础类型映射"""
    name: str                # AUTOSAR 名称, 如 "uint8"
    native_declaration: str  # C 原生声明, 如 "unsigned char"
    size: int                # 位宽


@dataclass
class DataType:
    """应用数据类型"""
    name: str
    base_type: str  # 对应的 BaseType 名称


@dataclass
class Port:
    """SWC 端口"""
    name: str
    port_kind: str          # "P-PORT" (提供) 或 "R-PORT" (需求)
    interface_name: str     # 关联的接口名称
    data_element: str       # 接口中的数据元素名
    data_type: str          # 数据类型


@dataclass
class Runnable:
    """可运行实体"""
    name: str
    min_interval: float = 0.0  # 最小执行周期 (秒)
    events: List[str] = field(default_factory=list)


@dataclass
class SoftwareComponent:
    """软件组件"""
    name: str
    ports: List[Port] = field(default_factory=list)
    runnables: List[Runnable] = field(default_factory=list)


@dataclass
class Connector:
    """组件连接器"""
    name: str
    provider_swc: str
    provider_port: str
    requester_swc: str
    requester_port: str


@dataclass
class RteFunction:
    """生成的 RTE API 函数"""
    name: str               # 函数名, 如 "Rte_Write_SWC1_PPort_time"
    return_type: str        # 返回类型
    body: str               # 函数体
    comment: str = ""       # 注释


@dataclass
class RteFile:
    """生成的 RTE 文件"""
    filename: str
    includes: List[str] = field(default_factory=list)
    macros: List[str] = field(default_factory=list)
    type_defs: List[str] = field(default_factory=list)
    global_vars: List[str] = field(default_factory=list)
    functions: List[RteFunction] = field(default_factory=list)


class RteModule:
    """
    RTE 模块 — 中间模型的根节点

    对应 Java 项目中的 RteModule，包含所有需要生成的文件信息。
    """

    def __init__(self):
        self.base_types: List[BaseType] = []
        self.data_types: List[DataType] = []
        self.components: List[SoftwareComponent] = []
        self.connectors: List[Connector] = []
        self.files: List[RteFile] = []

    def find_component(self, name: str) -> Optional[SoftwareComponent]:
        for comp in self.components:
            if comp.name == name:
                return comp
        return None

    def find_base_type(self, name: str) -> Optional[BaseType]:
        for bt in self.base_types:
            if bt.name == name:
                return bt
        return None

    def get_all_port_data_pairs(self) -> list:
        """获取所有 (swc, port, data_element, data_type) 四元组"""
        result = []
        for comp in self.components:
            for port in comp.ports:
                result.append((comp.name, port.name, port.data_element, port.data_type))
        return result
