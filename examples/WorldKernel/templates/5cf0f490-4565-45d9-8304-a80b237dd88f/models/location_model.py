"""Auto-generated Location Pydantic model."""
from pydantic import BaseModel


class IdentityDim(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    description: str = ""
    考核顺序标记: str = ""  # world-specific
    秘密第九考场所标记: str = ""  # world-specific
    与海神传承层级对应: str = ""  # world-specific
    场所功能细分_修炼_居住_祭祀: str = ""  # world-specific


class AccessDim(BaseModel):
    permissions: str = ""
    access_level: str = ""
    access_conditions: str = ""
    需要海神之光印记: str = ""  # world-specific
    受波塞西监控许可: str = ""  # world-specific
    特定时辰或考核阶段开放: str = ""  # world-specific
    禁止携带额外魂导器或武器: str = ""  # world-specific
    进入需通过守护者测试: str = ""  # world-specific


class StateDim(BaseModel):
    current_state: str = ""
    ownership: str = ""
    capacity: int = 0
    能量稳定度: str = ""  # world-specific
    深渊渗透程度_黑化小舞影响: str = ""  # world-specific
    考核激活状态: str = ""  # world-specific
    当前天气影响: str = ""  # world-specific
    结界封印强度: str = ""  # world-specific


class LocationModel(BaseModel):
    identity: IdentityDim = IdentityDim()
    access: AccessDim = AccessDim()
    state: StateDim = StateDim()
