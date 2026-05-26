# -*- coding: utf-8 -*-
"""
Tests for EcoPolicy-AI Skills REST API Server
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from skills_api.server import app

client = TestClient(app)


def test_health_endpoint():
    """测试健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_root_endpoint():
    """测试根路径欢迎接口"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "EcoPolicy-AI Skills API" in data["message"]
    assert data["swagger_docs"] == "/docs"


def test_mcp_initialize():
    """测试 MCP 握手机制"""
    from skills_api.mcp_server import handle_initialize
    resp = handle_initialize(1, {})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "capabilities" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "ecopolicy-mcp-server"


def test_mcp_tools_list():
    """测试 MCP 工具获取机制并验证映射关系"""
    from skills_api.mcp_server import handle_tools_list
    resp = handle_tools_list(2)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    assert len(tools) > 0
    
    # 确认所有核心技能工具成功暴露
    tool_names = [t["name"] for t in tools]
    assert "fetch_policy_url" in tool_names
    assert "match_enterprise_policy" in tool_names
    assert "save_enterprise_profile" in tool_names

