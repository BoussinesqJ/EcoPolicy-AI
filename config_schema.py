# -*- coding: utf-8 -*-
"""
配置 Schema 验证

使用 pydantic 验证 YAML 配置文件格式，启动时快速失败。

用法：
  from config_schema import validate_config, validate_enterprise_profile
  
  # 验证 policy_monitor/config.yaml
  config = validate_config("policy_monitor/config.yaml")
  
  # 验证企业画像
  profile = validate_enterprise_profile("enterprises/test/profile.yaml")
"""

from typing import Optional, List, Dict, Any
from pathlib import Path

import yaml

try:
    from pydantic import BaseModel, Field, validator
except ImportError:
    # 如果 pydantic 未安装，提供简单替代
    class BaseModel:
        """简单替代（无验证）"""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    def Field(default=None, **kwargs):
        return default
    
    def validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# ============================================================
# 数据源配置 Schema
# ============================================================

class PolicySource(BaseModel):
    """单个政策数据源配置"""
    name: str
    url: str
    type: str = "api"  # api / html
    frequency: str = "daily"  # daily / weekly
    enabled: bool = True
    note: Optional[str] = None
    selectors: Optional[Dict[str, str]] = None


class SafetyConfig(BaseModel):
    """安全策略配置"""
    min_delay_seconds: int = Field(default=30, ge=0)
    max_delay_seconds: int = Field(default=60, ge=0)
    max_pages_per_source: int = Field(default=2, ge=1)
    respect_robots: bool = True
    timeout_seconds: int = Field(default=15, ge=1)
    max_retries: int = Field(default=2, ge=0)
    user_agents: List[str] = []


class ScoringConfig(BaseModel):
    """评分配置"""
    p0_threshold: int = Field(default=6, ge=1)
    p1_threshold: int = Field(default=3, ge=1)


class RegionsConfig(BaseModel):
    """地区配置"""
    dir: str = "regions"
    default: Optional[str] = None
    include_national: bool = True


class SchedulerConfig(BaseModel):
    """调度器配置"""
    enabled: bool = False
    enterprise_id: str = ""
    region: Optional[str] = None
    industry: Optional[str] = None
    schedule_type: str = "daily_8am"
    auto_report: bool = True
    report_max_count: int = Field(default=5, ge=1)
    notify_email: Optional[str] = None


class MonitorConfig(BaseModel):
    """policy_monitor/config.yaml 完整配置"""
    sources: List[PolicySource] = []
    safety: SafetyConfig = SafetyConfig()
    scoring: ScoringConfig = ScoringConfig()
    regions: RegionsConfig = RegionsConfig()
    scheduler: SchedulerConfig = SchedulerConfig()


# ============================================================
# 企业画像 Schema
# ============================================================

class BasicInfo(BaseModel):
    """企业基本信息"""
    company_name: str
    short_name: str
    unified_credit_code: Optional[str] = None
    registered_capital: float = 0
    paid_in_capital: Optional[float] = None
    establishment_date: Optional[str] = None
    registered_address: str = ""
    actual_address: Optional[str] = None
    employee_count: Optional[int] = None
    legal_representative: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None


class IndustryInfo(BaseModel):
    """行业信息"""
    primary_sector: str
    sub_sector: str
    industry_keywords: List[str] = []
    business_scope: Optional[str] = None
    main_products: List[str] = []
    market_coverage: List[str] = []


class Qualifications(BaseModel):
    """企业资质"""
    high_tech_enterprise: bool = False
    sme_specialized: bool = False
    sme_specialized_level: Optional[str] = None
    gazelle_enterprise: bool = False
    unicorn_enterprise: bool = False
    listed: bool = False
    listing_board: Optional[str] = None
    listing_code: Optional[str] = None
    iso_certifications: List[str] = []
    other_qualifications: List[str] = []


class InnovationInfo(BaseModel):
    """创新与知识产权"""
    rd_investment_ratio: Optional[float] = None
    rd_personnel_count: Optional[int] = None
    invention_patents: int = 0
    utility_patents: int = 0
    design_patents: int = 0
    software_copyrights: int = 0
    research_platforms: List[str] = []
    cooperation_partners: List[str] = []


class RegionsInfo(BaseModel):
    """区域布局"""
    headquarters: str = ""
    branch_offices: List[str] = []
    production_locations: List[str] = []
    target_markets: List[str] = []
    overseas_markets: List[str] = []


class StrategyInfo(BaseModel):
    """战略方向"""
    short_term_goals: List[str] = []
    medium_term_goals: List[str] = []
    key_challenges: List[str] = []
    policy_needs: List[str] = []


class EnterpriseProfile(BaseModel):
    """企业画像完整配置"""
    basic_info: BasicInfo
    industry: IndustryInfo
    qualifications: Qualifications = Qualifications()
    innovation: Optional[InnovationInfo] = None
    regions: RegionsInfo = RegionsInfo()
    strategy: StrategyInfo = StrategyInfo()


# ============================================================
# 验证函数
# ============================================================

def validate_config(config_path: str) -> MonitorConfig:
    """验证 policy_monitor/config.yaml
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        MonitorConfig 对象
        
    Raises:
        ValueError: 验证失败
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"配置文件为空: {config_path}")
    
    try:
        return MonitorConfig(**data)
    except Exception as e:
        raise ValueError(f"配置验证失败 ({config_path}): {e}")


def validate_enterprise_profile(profile_path: str) -> EnterpriseProfile:
    """验证企业画像配置
    
    Args:
        profile_path: 企业画像文件路径
        
    Returns:
        EnterpriseProfile 对象
        
    Raises:
        ValueError: 验证失败
    """
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"企业画像文件不存在: {profile_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data:
        raise ValueError(f"企业画像文件为空: {profile_path}")
    
    # 检查必填字段
    required_sections = ["basic_info", "industry"]
    for section in required_sections:
        if section not in data:
            raise ValueError(f"缺少必填节: {section}")
    
    try:
        return EnterpriseProfile(**data)
    except Exception as e:
        raise ValueError(f"企业画像验证失败 ({profile_path}): {e}")


def validate_all_configs(base_dir: str) -> Dict[str, Any]:
    """验证项目所有配置文件
    
    Args:
        base_dir: 项目根目录
        
    Returns:
        验证结果字典
    """
    results = {
        "success": True,
        "errors": [],
        "warnings": [],
    }
    
    base = Path(base_dir)
    
    # 1. 验证 monitor 配置
    monitor_config_path = base / "policy_monitor" / "config.yaml"
    if monitor_config_path.exists():
        try:
            validate_config(str(monitor_config_path))
            results["monitor_config"] = "PASS"
        except (ValueError, FileNotFoundError) as e:
            results["monitor_config"] = "FAIL"
            results["errors"].append(f"monitor_config: {e}")
            results["success"] = False
    else:
        results["warnings"].append("monitor_config: 文件不存在")
    
    # 2. 验证企业画像
    enterprises_dir = base / "enterprises"
    if enterprises_dir.exists():
        for ent_dir in enterprises_dir.iterdir():
            if ent_dir.is_dir() and ent_dir.name != "_template":
                profile_path = ent_dir / "profile.yaml"
                if profile_path.exists():
                    try:
                        validate_enterprise_profile(str(profile_path))
                        results[f"enterprise_{ent_dir.name}"] = "PASS"
                    except (ValueError, FileNotFoundError) as e:
                        results[f"enterprise_{ent_dir.name}"] = "FAIL"
                        results["errors"].append(f"enterprise_{ent_dir.name}: {e}")
                        results["success"] = False
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = str(Path(__file__).parent.parent)
    
    print(f"验证配置文件: {base_dir}")
    results = validate_all_configs(base_dir)
    
    print(f"\n{'='*50}")
    print(f"  配置验证结果")
    print(f"{'='*50}")
    
    for key, value in results.items():
        if key not in ("success", "errors", "warnings"):
            status = "[PASS]" if value == "PASS" else "[FAIL]"
            print(f"  {status} {key}")
    
    if results["errors"]:
        print(f"\n  错误:")
        for err in results["errors"]:
            print(f"    - {err}")
    
    if results["warnings"]:
        print(f"\n  警告:")
        for warn in results["warnings"]:
            print(f"    - {warn}")
    
    print(f"\n  总结: {'全部通过' if results['success'] else '存在错误'}")
    print(f"{'='*50}")
    
    sys.exit(0 if results["success"] else 1)
