"""
ARXML 解析层 (AUTOSAR XML Parser)

对应 Java 项目中 persist 模块的功能:
  1. 解析 AUTOSAR XML 文件
  2. 解析 XSD Schema 中定义的基础类型
  3. 构建中间模型

支持解析的 AUTOSAR 元素:
  - SW-BASE-TYPE (基础类型)
  - APPLICATION-SW-COMPONENT-TYPE (应用组件)
  - P-PORT-PROTOTYPE / R-PORT-PROTOTYPE (端口)
  - RUNNABLE-ENTITY (可运行实体)
  - TIMING-EVENT (定时事件)
  - COMPOSITION-SW-COMPONENT-TYPE (组合组件及连接器)
"""

import xml.etree.ElementTree as ET
from intermediate_model import (
    BaseType, DataType, Port, Runnable,
    SoftwareComponent, Connector, RteModule,
)

# AUTOSAR 4.0.3 命名空间
AR_NS = "http://autosar.org/schema/r4.0"


def _tag(local: str) -> str:
    """生成带命名空间的标签名"""
    return f"{{{AR_NS}}}{local}"


def _text(parent: ET.Element, tag: str, default: str = "") -> str:
    """安全获取子元素文本"""
    el = parent.find(_tag(tag))
    return el.text.strip() if el is not None and el.text else default


def _shortname(parent: ET.Element) -> str:
    return _text(parent, "SHORT-NAME")


class ArxmlParser:
    """
    AUTOSAR XML 解析器

    将一个或多个 ARXML 文件解析并合并为一个 RteModule 中间模型。
    """

    def __init__(self):
        self._base_types: dict[str, BaseType] = {}
        self._interfaces: dict[str, dict] = {}   # interface_name -> {data_element, data_type}
        self._components: dict[str, SoftwareComponent] = {}
        self._connectors: list[Connector] = []

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def parse(self, *arxml_paths: str) -> RteModule:
        """解析多个 ARXML 文件，返回合并后的 RteModule"""
        for path in arxml_paths:
            tree = ET.parse(path)
            root = tree.getroot()
            self._parse_root(root)

        return self._build_module()

    # ------------------------------------------------------------------
    # 内部解析逻辑
    # ------------------------------------------------------------------

    def _parse_root(self, root: ET.Element):
        """遍历 AR-PACKAGES"""
        for ar_pkg in root.iter(_tag("AR-PACKAGE")):
            pkg_name = _shortname(ar_pkg)
            elements = ar_pkg.find(_tag("ELEMENTS"))
            if elements is None:
                # 可能是嵌套的 AR-PACKAGE
                for sub_pkg in ar_pkg.iter(_tag("AR-PACKAGE")):
                    sub_elements = sub_pkg.find(_tag("ELEMENTS"))
                    if sub_elements is not None:
                        self._parse_elements(sub_elements)
                continue
            self._parse_elements(elements)

    def _parse_elements(self, elements: ET.Element):
        """解析 ELEMENTS 下的所有元素"""
        for child in elements:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "SW-BASE-TYPE":
                self._parse_base_type(child)
            elif tag == "SENDER-RECEIVER-INTERFACE":
                self._parse_sender_receiver_interface(child)
            elif tag == "APPLICATION-SW-COMPONENT-TYPE":
                self._parse_application_swc(child)
            elif tag == "COMPOSITION-SW-COMPONENT-TYPE":
                self._parse_composition_swc(child)

    # -- 基础类型 --

    def _parse_base_type(self, el: ET.Element):
        name = _shortname(el)
        native = _text(el, "NATIVE-DECLARATION", "uint8")
        size = int(_text(el, "BASE-TYPE-SIZE", "8"))
        self._base_types[name] = BaseType(name=name, native_declaration=native, size=size)

    # -- Sender-Receiver 接口 --

    def _parse_sender_receiver_interface(self, el: ET.Element):
        name = _shortname(el)
        data_element = ""
        data_type = ""

        # VARIABLE-DATA-PROTOTYPE
        vdp = el.find(_tag("DATA-ELEMENTS"))
        if vdp is None:
            vdp = el  # 兼容旧格式
        for var in vdp.iter(_tag("VARIABLE-DATA-PROTOTYPE")):
            data_element = _shortname(var)
            type_ref = var.find(_tag("TYPE-TREF"))
            if type_ref is not None and type_ref.text:
                data_type = type_ref.text.strip().split("/")[-1]

        self._interfaces[name] = {
            "data_element": data_element,
            "data_type": data_type,
        }

    # -- 应用 SWC --

    def _parse_application_swc(self, el: ET.Element):
        swc_name = _shortname(el)
        ports = self._parse_ports(el)
        runnables = self._parse_internal_behaviors(el)

        self._components[swc_name] = SoftwareComponent(
            name=swc_name,
            ports=ports,
            runnables=runnables,
        )

    def _parse_ports(self, swc_el: ET.Element) -> list[Port]:
        ports = []
        for port_tag, kind in [
            ("P-PORT-PROTOTYPE", "P-PORT"),
            ("R-PORT-PROTOTYPE", "R-PORT"),
        ]:
            for pp in swc_el.iter(_tag(port_tag)):
                port_name = _shortname(pp)
                iface_ref_tag = "PROVIDED-INTERFACE-TREF" if kind == "P-PORT" else "REQUIRED-INTERFACE-TREF"
                iface_ref = pp.find(_tag(iface_ref_tag))
                iface_name = ""
                if iface_ref is not None and iface_ref.text:
                    iface_name = iface_ref.text.strip().split("/")[-1]

                # 查找接口中的数据信息
                data_element = ""
                data_type = ""
                if iface_name in self._interfaces:
                    data_element = self._interfaces[iface_name]["data_element"]
                    data_type = self._interfaces[iface_name]["data_type"]

                ports.append(Port(
                    name=port_name,
                    port_kind=kind,
                    interface_name=iface_name,
                    data_element=data_element,
                    data_type=data_type,
                ))
        return ports

    def _parse_internal_behaviors(self, swc_el: ET.Element) -> list[Runnable]:
        runnables = []
        for behavior in swc_el.iter(_tag("SWC-INTERNAL-BEHAVIOR")):
            for run_el in behavior.iter(_tag("RUNNABLE-ENTITY")):
                run_name = _shortname(run_el)
                min_interval = 0.0
                events = []

                # 解析 TIMING-EVENT
                for timing in behavior.iter(_tag("TIMING-EVENT")):
                    start_ref = timing.find(_tag("START-ON-EVENT-REF"))
                    if start_ref is not None and start_ref.text:
                        ref_name = start_ref.text.strip().split("/")[-1]
                        if ref_name == run_name:
                            period = _text(timing, "PERIOD", "0")
                            min_interval = float(period)
                            events.append(f"TimingEvent({period}s)")

                runnables.append(Runnable(
                    name=run_name,
                    min_interval=min_interval,
                    events=events,
                ))
        return runnables

    # -- 组合 SWC (连接器) --

    def _parse_composition_swc(self, el: ET.Element):
        for connector in el.iter(_tag("ASSEMBLY-SW-CONNECTOR")):
            cn_name = _shortname(connector)

            prov_iref = connector.find(_tag("PROVIDER-IREF"))
            req_iref = connector.find(_tag("REQUESTER-IREF"))

            if prov_iref is None or req_iref is None:
                continue

            prov_comp_ref = prov_iref.find(_tag("CONTEXT-COMPONENT-REF"))
            prov_port_ref = prov_iref.find(_tag("TARGET-P-PORT-REF"))
            req_comp_ref = req_iref.find(_tag("CONTEXT-COMPONENT-REF"))
            req_port_ref = req_iref.find(_tag("TARGET-R-PORT-REF"))

            def _ref_name(ref_el):
                if ref_el is not None and ref_el.text:
                    return ref_el.text.strip().split("/")[-1]
                return ""

            self._connectors.append(Connector(
                name=cn_name,
                provider_swc=_ref_name(prov_comp_ref),
                provider_port=_ref_name(prov_port_ref),
                requester_swc=_ref_name(req_comp_ref),
                requester_port=_ref_name(req_port_ref),
            ))

    # ------------------------------------------------------------------
    # 构建中间模型
    # ------------------------------------------------------------------

    def _build_module(self) -> RteModule:
        module = RteModule()
        module.base_types = list(self._base_types.values())
        module.components = list(self._components.values())
        module.connectors = self._connectors

        # 构建 DataType
        for comp in module.components:
            for port in comp.ports:
                if port.data_type and port.data_type in self._base_types:
                    module.data_types.append(DataType(
                        name=port.data_type,
                        base_type=port.data_type,
                    ))

        # 去重
        seen = set()
        unique_types = []
        for dt in module.data_types:
            if dt.name not in seen:
                seen.add(dt.name)
                unique_types.append(dt)
        module.data_types = unique_types

        return module
