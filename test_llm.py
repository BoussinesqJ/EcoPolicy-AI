# -*- coding: utf-8 -*-
"""
Test script for EcoPolicy AI Agent
Supports live testing (if API key is present) and mock testing (offline validation).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Ensure project root is in path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from ai_agent.llm import LLMClient
from ai_agent.analyst import PolicyAnalystAgent
from ai_agent.tools import TOOL_SCHEMAS, execute_tool


class TestAgentWorkflow(unittest.TestCase):
    """测试智能体的工作流与工具调用"""

    def setUp(self):
        # 确保 enterprises 目录和 jyuh 企业存在
        self.enterprise_id = "jyuh"
        self.profile_dir = BASE_DIR / "enterprises" / self.enterprise_id
        self.workspace_dir = self.profile_dir / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    @patch("openai.resources.chat.completions.Completions.create")
    def test_react_loop_with_mocks(self, mock_create):
        """测试 ReAct 循环与 Function Calling 的模拟调用"""
        print("\n=== 开始 Mock 离线测试 ReAct 循环 ===")

        # 1. 模拟 OpenAI 客户端 API 返回结构
        # Turn 1: 模拟模型选择调用 match_enterprise_policy 和 calculate_policy_roi
        mock_choice_1 = MagicMock()
        mock_choice_1.message.content = "我需要先评估这项政策与 jyuh 企业的匹配度以及 ROI。"
        
        tool_call_1 = MagicMock()
        tool_call_1.id = "call_1"
        tool_call_1.type = "function"
        tool_call_1.function.name = "match_enterprise_policy"
        tool_call_1.function.arguments = '{"enterprise_id": "jyuh", "policy_title": "测试高新技术企业补贴政策", "policy_summary": "向符合条件的高新技术企业提供100万元研发补贴。"}'
        
        tool_call_2 = MagicMock()
        tool_call_2.id = "call_2"
        tool_call_2.type = "function"
        tool_call_2.function.name = "calculate_policy_roi"
        tool_call_2.function.arguments = '{"enterprise_id": "jyuh", "policy_title": "测试高新技术企业补贴政策", "policy_summary": "向符合条件的高新技术企业提供100万元研发补贴。", "success_probability": 0.9}'
        
        mock_choice_1.message.tool_calls = [tool_call_1, tool_call_2]

        # Turn 2: 模拟模型决定编写报告并保存
        mock_choice_2 = MagicMock()
        mock_choice_2.message.content = "匹配评分和 ROI 已经计算完成，我现在来生成正式报告并保存。"
        
        tool_call_3 = MagicMock()
        tool_call_3.id = "call_3"
        tool_call_3.type = "function"
        tool_call_3.function.name = "write_markdown_report"
        tool_call_3.function.arguments = '{"enterprise_id": "jyuh", "filename": "policy_analysis_test.md", "markdown_content": "# 政策匹配分析报告\\n\\n> **一句话判断**：测试高企政策与jyuh完美匹配，ROI达9.0倍。\\n\\n## 一、政策速览\\n- 名称：测试高新技术企业补贴政策\\n- 来源：测试单位\\n\\n## 二、硬性条件比对\\n- 通过\\n"}'
        
        mock_choice_2.message.tool_calls = [tool_call_3]

        # Turn 3: 模拟模型完成全部任务
        mock_choice_3 = MagicMock()
        mock_choice_3.message.content = "测试政策的匹配分析已完成，报告已成功保存至 `enterprises/jyuh/workspace/policy_analysis_test.md`。"
        mock_choice_3.message.tool_calls = None

        # 设置 mock API 依次返回这些响应
        mock_resp_1 = MagicMock()
        mock_resp_1.choices = [mock_choice_1]
        
        mock_resp_2 = MagicMock()
        mock_resp_2.choices = [mock_choice_2]
        
        mock_resp_3 = MagicMock()
        mock_resp_3.choices = [mock_choice_3]
        
        mock_create.side_effect = [mock_resp_1, mock_resp_2, mock_resp_3]

        # 2. 运行 Agent Analyst
        # 使用虚拟 Key 初始化以启用客户端
        with patch.dict(os.environ, {"ECOPOLICY_API_KEY": "dummy_key"}):
            agent = PolicyAnalystAgent()
            prompt = "帮我分析测试高企政策（额度100万，高企认定补贴）对 jyuh 企业的适配度，计算 ROI 并生成 Markdown 报告保存。"
            final_answer = agent.run(prompt, enterprise_id=self.enterprise_id)
            
            # 3. 验证断言
            self.assertIn("policy_analysis_test.md", final_answer)
            self.assertTrue(mock_create.called)
            
            # 检查报告文件是否生成
            report_file = self.workspace_dir / "policy_analysis_test.md"
            self.assertTrue(report_file.exists())
            
            # 读取内容验证
            with open(report_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("一句话判断", content)
            self.assertIn("jyuh", content)
            
            print("[OK] Mock 离线测试 ReAct 循环成功！")


def run_live_test():
    """如果配置了 API Key，执行真实 API 连接测试"""
    api_key = os.environ.get("ECOPOLICY_API_KEY") or \
              os.environ.get("DEEPSEEK_API_KEY") or \
              os.environ.get("OPENAI_API_KEY")
              
    if not api_key:
        print("\n[!] 未配置 API Key，跳过真实 API 连接测试。")
        print("    如果你想测试真实 API 连接，请先配置环境变量 ECOPOLICY_API_KEY。")
        return
        
    print("\n=== 开始真实 API 连通性测试 ===")
    client = LLMClient()
    if not client.is_available():
        print("[!] 客户端初始化失败")
        return
        
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, please reply with 'pong' only."}
    ]
    try:
        response = client.chat_completion(messages=messages)
        content = response.choices[0].message.content.strip()
        print(f"[✔] API 连接成功，模型回复: '{content}'")
    except Exception as e:
        print(f"[!] API 连接测试失败: {e}")


if __name__ == "__main__":
    # 1. 运行 Unit Tests (Mock)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAgentWorkflow)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 2. 运行真实 API 连通性测试
    run_live_test()
    
    # 退出码
    sys.exit(not result.wasSuccessful())
