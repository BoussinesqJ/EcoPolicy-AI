# -*- coding: utf-8 -*-
"""
EcoPolicy AI Agent Tools
Provides Python implementation of agent tools and OpenAI-compatible JSON schemas.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Resolve project base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Import crawler/parser functions
import sys
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "policy_monitor"))

from policy_monitor.parsers.user_upload import parse_url, parse_file, parse_text
from policy_monitor.database import PolicyDatabase
from enterprise_matcher import EnterpriseMatcher
from roi_calculator import ROICalculator, classify_policy_type
from policy_stacker import PolicyStacker

logger = logging.getLogger("ecopolicy.agent.tools")


# ============================================================
# Python Tool Implementations
# ============================================================

def fetch_policy_url(url: str) -> Dict[str, Any]:
    """抓取指定网页政策链接并返回结构化数据"""
    try:
        logger.info(f"Tool call: fetch_policy_url({url})")
        policy = parse_url(url)
        return {
            "status": "success",
            "title": policy.get("title", ""),
            "date": policy.get("date", ""),
            "source": policy.get("source", ""),
            "summary": policy.get("summary", ""),
            "content": policy.get("content", "")
        }
    except Exception as e:
        logger.error(f"fetch_policy_url failed: {e}")
        return {"status": "error", "message": str(e)}


def parse_policy_file(file_path: str) -> Dict[str, Any]:
    """解析本地 PDF/Word/Text 政策文件"""
    try:
        logger.info(f"Tool call: parse_policy_file({file_path})")
        # Ensure path is resolved correctly (could be absolute or relative to workspace)
        target_path = Path(file_path)
        if not target_path.is_absolute():
            target_path = BASE_DIR / target_path

        policy = parse_file(str(target_path))
        return {
            "status": "success",
            "title": policy.get("title", ""),
            "date": policy.get("date", ""),
            "source": policy.get("source", ""),
            "summary": policy.get("summary", ""),
            "content": policy.get("content", "")
        }
    except Exception as e:
        logger.error(f"parse_policy_file failed: {e}")
        return {"status": "error", "message": str(e)}


def query_database_policies(limit: int = 20, days: int = 7) -> Dict[str, Any]:
    """从 SQLite 数据库获取最近几天的抓取政策"""
    try:
        logger.info(f"Tool call: query_database_policies(limit={limit}, days={days})")
        db_path = BASE_DIR / "policy_data" / "policies.db"
        data_dir = BASE_DIR / "policy_data"
        
        if not db_path.exists():
            return {
                "status": "success",
                "policies": [],
                "message": "数据库不存在，尚无抓取的政策记录。"
            }
            
        db = PolicyDatabase(str(db_path), str(data_dir))
        policies = db.get_recent_policies(days=days)
        db.close()
        
        # Limit the results
        policies = policies[:limit]
        
        # Format policies to avoid returning too much raw content (keeping summary only)
        formatted_policies = []
        for p in policies:
            formatted_policies.append({
                "url_hash": p.get("url_hash", ""),
                "title": p.get("title", ""),
                "url": p.get("url", ""),
                "date": p.get("date", ""),
                "source": p.get("source", ""),
                "priority": p.get("priority", "P2"),
                "score": p.get("score", 0),
                "summary": p.get("summary", "")[:800] + ("..." if len(p.get("summary", "")) > 800 else "")
            })
            
        return {
            "status": "success",
            "count": len(formatted_policies),
            "policies": formatted_policies
        }
    except Exception as e:
        logger.error(f"query_database_policies failed: {e}")
        return {"status": "error", "message": str(e)}


def match_enterprise_policy(enterprise_id: str, policy_title: str, policy_summary: str, policy_url: str = "") -> Dict[str, Any]:
    """运行四维匹配评分与硬性条件检查，返回详细评分结构"""
    try:
        logger.info(f"Tool call: match_enterprise_policy({enterprise_id}, {policy_title[:20]})")
        enterprises_dir = BASE_DIR / "enterprises"
        matcher = EnterpriseMatcher(str(enterprises_dir))
        
        if enterprise_id not in matcher.get_enterprise_ids():
            return {
                "status": "error",
                "message": f"未找到企业 ID '{enterprise_id}'，可用企业: {', '.join(matcher.get_enterprise_ids())}"
            }
            
        policy_dict = {
            "title": policy_title,
            "summary": policy_summary,
            "url": policy_url or "https://unknown.gov.cn/policy",
            "source": policy_url or "未知来源",
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        
        results = matcher.match_policies([policy_dict], enterprise_id)
        if not results:
            # Let's run raw matching manually to show why it failed
            ent = matcher.enterprises[enterprise_id]
            res = matcher._match_single(policy_dict, ent)
            if res:
                return {
                    "status": "success",
                    "matched": False,
                    "reason": "匹配评分低于 3/5 分阈值",
                    "detail": res.to_dict()
                }
            return {
                "status": "success",
                "matched": False,
                "reason": "完全不匹配"
            }
            
        return {
            "status": "success",
            "matched": True,
            "detail": results[0].to_dict()
        }
    except Exception as e:
        logger.error(f"match_enterprise_policy failed: {e}")
        return {"status": "error", "message": str(e)}


def calculate_policy_roi(enterprise_id: str, policy_title: str, policy_summary: str, success_probability: float) -> Dict[str, Any]:
    """量化计算申报该政策的 ROI、收益、合规成本"""
    try:
        logger.info(f"Tool call: calculate_policy_roi({enterprise_id}, {policy_title[:20]}, prob={success_probability})")
        enterprises_dir = BASE_DIR / "enterprises"
        matcher = EnterpriseMatcher(str(enterprises_dir))
        
        if enterprise_id not in matcher.get_enterprise_ids():
            return {
                "status": "error",
                "message": f"未找到企业 ID '{enterprise_id}'"
            }
            
        ent = matcher.enterprises[enterprise_id]
        profile = ent.get("profile", {})
        industry = profile.get("industry", {}).get("primary_sector", "通用")
        
        calc = ROICalculator(industry=industry)
        policy_dict = {
            "title": policy_title,
            "summary": policy_summary,
        }
        
        financials = calc.estimate_financials(policy_dict, profile)
        roi_result = calc.calculate(financials, success_probability)
        
        return {
            "status": "success",
            "roi_ratio": roi_result.roi_ratio,
            "verdict": roi_result.verdict,
            "total_benefit": roi_result.total_benefit,
            "risk_adjusted_benefit": roi_result.risk_adjusted_benefit,
            "total_cost": roi_result.total_cost,
            "payback_months": roi_result.payback_months,
            "detail": roi_result.to_dict()
        }
    except Exception as e:
        logger.error(f"calculate_policy_roi failed: {e}")
        return {"status": "error", "message": str(e)}


def optimize_policy_stacking(enterprise_id: str, policies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算多条政策的互斥性，生成最优推荐组合和收入天花板"""
    try:
        logger.info(f"Tool call: optimize_policy_stacking({enterprise_id}, count={len(policies)})")
        enterprises_dir = BASE_DIR / "enterprises"
        matcher = EnterpriseMatcher(str(enterprises_dir))
        
        if enterprise_id not in matcher.get_enterprise_ids():
            return {
                "status": "error",
                "message": f"未找到企业 ID '{enterprise_id}'"
            }
            
        ent = matcher.enterprises[enterprise_id]
        profile = ent.get("profile", {})
        industry = profile.get("industry", {}).get("primary_sector", "通用")
        
        # Prepare stacker input (run matching and ROI dynamically for each input policy if needed)
        stacking_input = []
        for idx, p in enumerate(policies):
            title = p.get("title", f"Policy_{idx}")
            summary = p.get("summary", "")
            url = p.get("url", "")
            
            # 1. Run matching to get success probability and recommendation score
            policy_dict = {"title": title, "summary": summary, "url": url, "source": url}
            match_res = matcher._match_single(policy_dict, ent)
            
            prob = p.get("success_probability") or (match_res.success_probability if match_res else 0.5)
            rec_score = p.get("recommendation_score") or (match_res.recommendation_score if match_res else 3)
            
            # 2. Estimate ROI
            calc = ROICalculator(industry=industry)
            financials = calc.estimate_financials(policy_dict, profile)
            roi_res = calc.calculate(financials, prob)
            
            p_type = classify_policy_type(title, summary)
            
            stacking_input.append({
                "policy": policy_dict,
                "roi_ratio": roi_res.roi_ratio,
                "benefit": roi_res.risk_adjusted_benefit,
                "cost": roi_res.total_cost,
                "policy_type": p_type,
                "recommendation": rec_score
            })
            
        if not stacking_input:
            return {
                "status": "error",
                "message": "未能生成有效的政策组合输入数据"
            }
            
        stacker = PolicyStacker()
        stacking_result = stacker.analyze(stacking_input, profile)
        
        # Serialize Result classes to dicts
        bundles_serialized = []
        for b in stacking_result.get("bundles", []):
            bundles_serialized.append({
                "name": b.name,
                "policies": b.policies,
                "total_benefit": b.total_benefit,
                "total_cost": b.total_cost,
                "net_benefit": b.net_benefit,
                "average_roi": b.average_roi,
                "description": b.description
            })
            
        ceiling_serialized = {
            "theoretical_max": stacking_result["ceiling"].theoretical_max,
            "feasible_max": stacking_result["ceiling"].feasible_max,
            "limited_by": stacking_result["ceiling"].limited_by,
            "reasons": stacking_result["ceiling"].reasons
        }
        
        # Convert tuple keys in pairwise dict to string keys for JSON compatibility
        pairwise_serialized = {}
        for (i, j), rule in stacking_result.get("pairwise", {}).items():
            pairwise_serialized[f"{i},{j}"] = {
                "rule": rule.get("rule", "unknown"),
                "reason": rule.get("reason", ""),
                "similarity": rule.get("similarity", 0.0)
            }
            
        return {
            "status": "success",
            "summary": stacking_result.get("summary", ""),
            "bundles": bundles_serialized,
            "ceiling": ceiling_serialized,
            "pairwise": pairwise_serialized
        }
    except Exception as e:
        logger.error(f"optimize_policy_stacking failed: {e}")
        return {"status": "error", "message": str(e)}


def write_markdown_report(enterprise_id: str, filename: str, markdown_content: str) -> Dict[str, Any]:
    """保存生成的 Markdown 报告到企业工作区"""
    try:
        logger.info(f"Tool call: write_markdown_report({enterprise_id}, {filename})")
        # Validate filename to prevent path traversal
        clean_filename = os.path.basename(filename)
        if not clean_filename.endswith(".md"):
            clean_filename += ".md"
            
        workspace_dir = BASE_DIR / "enterprises" / enterprise_id / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = workspace_dir / clean_filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        return {
            "status": "success",
            "filepath": str(filepath),
            "filename": clean_filename,
            "message": f"报告已成功保存至: enterprises/{enterprise_id}/workspace/{clean_filename}"
        }
    except Exception as e:
        logger.error(f"write_markdown_report failed: {e}")
        return {"status": "error", "message": str(e)}


def save_enterprise_profile(enterprise_id: str, profile_yaml: str) -> Dict[str, Any]:
    """保存或更新企业画像配置文件 (profile.yaml)"""
    try:
        logger.info(f"Tool call: save_enterprise_profile({enterprise_id})")
        import re
        clean_id = re.sub(r'[^\w-]', '', enterprise_id)
        if not clean_id:
            return {"status": "error", "message": "无效的企业 ID"}
            
        enterprise_dir = BASE_DIR / "enterprises" / clean_id
        enterprise_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = enterprise_dir / "profile.yaml"
        
        import yaml
        try:
            profile_data = yaml.safe_load(profile_yaml)
            if not isinstance(profile_data, dict):
                return {"status": "error", "message": "YAML 内容必须是一个字典对象"}
        except yaml.YAMLError as e:
            return {"status": "error", "message": f"YAML 解析失败: {e}"}
            
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile_data, f, allow_unicode=True)
            
        return {
            "status": "success",
            "enterprise_id": clean_id,
            "filepath": str(filepath),
            "message": f"企业画像已成功保存/更新至: enterprises/{clean_id}/profile.yaml"
        }
    except Exception as e:
        logger.error(f"save_enterprise_profile failed: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================
# Tool Registry Map
# ============================================================

TOOL_FUNCTIONS = {
    "fetch_policy_url": fetch_policy_url,
    "parse_policy_file": parse_policy_file,
    "query_database_policies": query_database_policies,
    "match_enterprise_policy": match_enterprise_policy,
    "calculate_policy_roi": calculate_policy_roi,
    "optimize_policy_stacking": optimize_policy_stacking,
    "write_markdown_report": write_markdown_report,
    "save_enterprise_profile": save_enterprise_profile,
}


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """根据名称和参数执行对应的工具"""
    if name not in TOOL_FUNCTIONS:
        return {"status": "error", "message": f"Tool '{name}' not found."}
    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except TypeError as e:
        return {"status": "error", "message": f"Invalid arguments for tool '{name}': {e}"}


# ============================================================
# OpenAI-Compatible Tool Schemas (Function Calling)
# ============================================================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_policy_url",
            "description": "抓取指定的政府/新闻政策网页链接，提取政策标题、发布日期、发布来源和正文内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "政策正文页面的 URL 链接"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_policy_file",
            "description": "读取并解析本地上传的政策文档文件，支持 PDF、Word (.docx) 以及纯文本 (.txt) 文件类型。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "本地政策文件的相对或绝对路径，如 'policy.pdf'"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database_policies",
            "description": "从本地 SQLite 数据库查询最近抓取的政策列表，用于自动驾驶模式下的政策扫描和定期更新。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "返回的政策最大数量，默认 20 条"
                    },
                    "days": {
                        "type": "integer",
                        "default": 7,
                        "description": "查询最近几天抓取的政策，默认 7 天内"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "match_enterprise_policy",
            "description": "将一条具体的政策与企业画像进行四维（技术端、生产端、市场端、资本端）匹配打分，并检查硬性条件是否通过。",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业 ID，例如 'jyuh'"
                    },
                    "policy_title": {
                        "type": "string",
                        "description": "政策标题"
                    },
                    "policy_summary": {
                        "type": "string",
                        "description": "政策摘要或正文内容"
                    },
                    "policy_url": {
                        "type": "string",
                        "description": "可选。政策网页链接"
                    }
                },
                "required": ["enterprise_id", "policy_title", "policy_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_policy_roi",
            "description": "根据政策分类财务模型和企业规模，估算企业申报该政策的财务指标（如最大扶持金额、税收减免、合规成本、申请成本、回本周期和 ROI 比例）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业 ID，例如 'jyuh'"
                    },
                    "policy_title": {
                        "type": "string",
                        "description": "政策标题"
                    },
                    "policy_summary": {
                        "type": "string",
                        "description": "政策摘要或核心内容（用于识别政策类型和具体额度）"
                    },
                    "success_probability": {
                        "type": "number",
                        "description": "申报成功概率（0.0 至 1.0），通常来自 match_enterprise_policy 结果中的 success_probability"
                    }
                },
                "required": ["enterprise_id", "policy_title", "policy_summary", "success_probability"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_policy_stacking",
            "description": "对多条目标匹配政策进行组合叠加分析，识别两两政策之间的互斥或互补关系，并利用贪心算法推荐出总收益最大且无冲突的最优组合方案以及预估政策收入天花板上限。",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业 ID，例如 'jyuh'"
                    },
                    "policies": {
                        "type": "array",
                        "description": "待评估叠加分析的政策字典列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {
                                    "type": "string",
                                    "description": "政策标题"
                                },
                                "summary": {
                                    "type": "string",
                                    "description": "政策摘要或内容"
                                },
                                "url": {
                                    "type": "string",
                                    "description": "可选。政策链接"
                                },
                                "success_probability": {
                                    "type": "number",
                                    "description": "可选。成功概率，不传则系统自动匹配估算"
                                },
                                "recommendation_score": {
                                    "type": "integer",
                                    "description": "可选。匹配推荐评分，不传则系统自动匹配估算"
                                }
                            },
                            "required": ["title", "summary"]
                        }
                    }
                },
                "required": ["enterprise_id", "policies"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_markdown_report",
            "description": "将大模型生成的专业 Markdown 经济政策分析报告或申报草稿材料，安全保存到该企业的本地工作区目录中。",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "企业 ID，例如 'jyuh'"
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存的文件名，如 'policy_analysis_report.md'"
                    },
                    "markdown_content": {
                        "type": "string",
                        "description": "完整的 Markdown 文本报告内容"
                    }
                },
                "required": ["enterprise_id", "filename", "markdown_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_enterprise_profile",
            "description": "保存或更新企业的 YAML 画像配置文件。这允许大模型从一段企业简介中提取关键结构化信息（如基本信息、行业、财务状况、资质和地区），并持久化登记到企业画像目录中，以便进行精确测算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "enterprise_id": {
                        "type": "string",
                        "description": "新建或更新的企业 ID，例如 'tencent' 或 'pinduoduo'"
                    },
                    "profile_yaml": {
                        "type": "string",
                        "description": "格式完备的 YAML 企业画像内容（字段结构必须包含 basic_info, industry, qualifications, regions, strategy 字段）"
                    }
                },
                "required": ["enterprise_id", "profile_yaml"]
            }
        }
    }
]
