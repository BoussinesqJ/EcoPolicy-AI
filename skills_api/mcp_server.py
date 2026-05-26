# -*- coding: utf-8 -*-
"""
Native MCP (Model Context Protocol) Server for EcoPolicy-AI Skills.
Allows IDEs like Trae, Cursor, Claude Desktop, and WorkBuddy to call policy tools over stdin/stdout.
Uses JSON-RPC 2.0 protocol and zero external dependencies.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Setup logging to stderr because stdout is reserved for JSON-RPC messages!
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("ecopolicy.mcp.server")

# Resolve project base directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_agent.tools import TOOL_SCHEMAS, execute_tool

# Ensure stdin/stdout use UTF-8 encoding on Windows to prevent encoding errors
try:
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    # Older Python versions fallback
    pass


def convert_openai_to_mcp_tools() -> List[Dict[str, Any]]:
    """将 OpenAI Function Calling Schema 动态转换为 MCP Tools Schema"""
    mcp_tools = []
    for item in TOOL_SCHEMAS:
        func = item["function"]
        mcp_tools.append({
            "name": func["name"],
            "description": func["description"],
            "inputSchema": func["parameters"]
        })
    return mcp_tools


def send_response(resp: Dict[str, Any]):
    """向 stdout 发送 JSON-RPC 响应，并刷新缓冲区"""
    try:
        payload = json.dumps(resp, ensure_ascii=False)
        sys.stdout.write(payload + "\n")
        sys.stdout.flush()
        logger.debug(f"Sent MCP Response: {payload[:200]}")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")


def handle_initialize(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """处理 initialize 握手协议"""
    logger.info("MCP initialize request received")
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "ecopolicy-mcp-server",
                "version": "1.0.0"
            }
        }
    }


def handle_tools_list(req_id: Any) -> Dict[str, Any]:
    """处理 tools/list 获取工具列表请求"""
    logger.info("MCP tools/list request received")
    tools = convert_openai_to_mcp_tools()
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": tools
        }
    }


def handle_tools_call(req_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
    """处理 tools/call 执行具体工具请求"""
    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    
    logger.info(f"MCP tools/call request: {tool_name}")
    
    try:
        # 执行对应工具并获得字典结果
        result_dict = execute_tool(tool_name, arguments)
        is_error = result_dict.get("status") == "error"
        
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_dict, ensure_ascii=False)
                    }
                ],
                "isError": is_error
            }
        }
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)
                    }
                ],
                "isError": True
            }
        }


def handle_request(line: str):
    """解析并分发 JSON-RPC 请求"""
    try:
        req = json.loads(line)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {e}")
        return

    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    # 1. initialize 握手
    if method == "initialize":
        resp = handle_initialize(req_id, params)
        send_response(resp)

    # 2. initialized 确认通知 (不需要回复)
    elif method == "notifications/initialized" or method == "initialized":
        logger.info("MCP server initialized successfully")
        
    # 3. 列出工具
    elif method == "tools/list":
        resp = handle_tools_list(req_id)
        send_response(resp)

    # 4. 调用工具
    elif method == "tools/call":
        resp = handle_tools_call(req_id, params)
        send_response(resp)

    # 5. 协议不支持的方法
    elif req_id is not None:
        logger.warning(f"Unsupported MCP method: {method}")
        send_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }
        })


def run_mcp_loop():
    """持续监听 stdin 管道输入"""
    logger.info("EcoPolicy-AI MCP Server starting...")
    logger.info("Listening on stdin for JSON-RPC messages...")
    
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            logger.debug(f"Received raw line: {line.strip()[:200]}")
            handle_request(line)
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user.")
    except Exception as e:
        logger.critical(f"MCP Server crashed: {e}")


if __name__ == "__main__":
    run_mcp_loop()
