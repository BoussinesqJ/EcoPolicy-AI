# -*- coding: utf-8 -*-
"""
测试配置和公共 fixtures
"""

import sys
from pathlib import Path

import pytest
import yaml

# 确保能导入项目模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "policy_monitor"))


@pytest.fixture
def sample_policy():
    """示例政策数据"""
    return {
        "title": "关于加快推进人工智能产业发展的实施意见",
        "url": "https://www.example.gov.cn/policy/2026/001",
        "date": "2026-05-20",
        "source": "国务院-人工智能",
        "summary": "支持大模型、深度学习、计算机视觉等关键技术研究，单个项目最高补助500万元。对首次认定为国家级专精特新小巨人企业的人工智能企业，给予100万元奖励。",
        "content": "各市州人民政府，省政府各部门：为深入贯彻落实国家新一代人工智能发展规划...",
        "keywords_matched": ["人工智能", "大模型", "专精特新"],
        "score": 8,
        "priority": "P0",
        "fetched_at": "2026-05-25T10:00:00",
    }


@pytest.fixture
def sample_enterprise_profile():
    """示例企业画像"""
    return {
        "basic_info": {
            "company_name": "DEMO示例企业",
            "short_name": "DEMO企业",
            "registered_capital": 5000,
            "registered_address": "湖北省武汉市",
        },
        "industry": {
            "primary_sector": "数字经济",
            "sub_sector": "人工智能",
            "industry_keywords": ["人工智能", "大模型", "智能制造", "工业互联网"],
        },
        "qualifications": {
            "high_tech_enterprise": True,
            "sme_specialized": True,
            "sme_specialized_level": "省级",
        },
        "regions": {
            "headquarters": "湖北",
        },
        "strategy": {
            "policy_needs": ["资金补贴", "税收优惠", "人才引进"],
        },
    }


@pytest.fixture
def sample_enterprise_dir(tmp_path, sample_enterprise_profile):
    """创建临时企业目录"""
    ent_dir = tmp_path / "test_enterprise"
    ent_dir.mkdir()
    
    profile_path = ent_dir / "profile.yaml"
    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.dump(sample_enterprise_profile, f, allow_unicode=True)
    
    return tmp_path


@pytest.fixture
def sample_html():
    """示例 HTML 内容"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>关于加快推进人工智能产业发展的实施意见</title></head>
    <body>
        <h1>关于加快推进人工智能产业发展的实施意见</h1>
        <div class="content">
            <p>各市州人民政府，省政府各部门：</p>
            <p>为深入贯彻落实国家新一代人工智能发展规划，加快推进我省人工智能产业高质量发展，现提出以下实施意见：</p>
            <p>一、总体目标</p>
            <p>到2027年，人工智能核心产业规模达到500亿元。</p>
        </div>
        <div class="date">2026-05-20</div>
    </body>
    </html>
    """


@pytest.fixture
def sample_api_response():
    """示例 API 响应（国务院搜索格式）"""
    return """
    {
        "searchVO": {
            "listVO": [
                {
                    "title": "关于加快推进人工智能产业发展的实施意见",
                    "url": "https://www.example.gov.cn/policy/2026/001",
                    "pubtime": "1716182400000",
                    "summary": "支持大模型、深度学习等关键技术研究"
                }
            ]
        }
    }
    """
