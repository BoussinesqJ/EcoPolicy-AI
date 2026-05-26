# -*- coding: utf-8 -*-
"""
EcoPolicy AI Agent Analyst Engine
Implements the autonomous ReAct (Reason-Action-Observation) loop using Function Calling.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from ai_agent.llm import LLMClient
from ai_agent.tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger("ecopolicy.agent.analyst")
BASE_DIR = Path(__file__).resolve().parent.parent


class PolicyAnalystAgent:
    """经济政策分析智能体控制中心"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        
    def _load_enterprise_context(self, enterprise_id: str) -> str:
        """加载企业画像与偏好设置作为上下文"""
        context_parts = []
        
        # 1. 加载企业基本画像
        profile_path = BASE_DIR / "enterprises" / enterprise_id / "profile.yaml"
        if profile_path.exists():
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    profile_content = f.read()
                context_parts.append(f"### 企业画像 (enterprises/{enterprise_id}/profile.yaml):\n```yaml\n{profile_content}\n```")
            except Exception as e:
                logger.error(f"加载企业画像失败: {e}")
                
        # 2. 加载企业自定义评分偏好
        prefs_path = BASE_DIR / "enterprises" / enterprise_id / "preferences.yaml"
        if prefs_path.exists():
            try:
                with open(prefs_path, "r", encoding="utf-8") as f:
                    prefs_content = f.read()
                context_parts.append(f"### 企业匹配与评估偏好 (enterprises/{enterprise_id}/preferences.yaml):\n```yaml\n{prefs_content}\n```")
            except Exception as e:
                logger.error(f"加载企业偏好失败: {e}")
                
        if context_parts:
            return "\n\n".join(context_parts)
        return "未提供或未找到指定企业 ID 的画像上下文。"

    def run(self, prompt: str, enterprise_id: Optional[str] = None, max_turns: int = 10) -> str:
        """执行自主 ReAct 规划与工具调用循环"""
        if not self.llm.is_available():
            return "错误: 大模型 API 客户端不可用，请配置 API Key 后再试。"

        print(f"\n[*] 启动 EcoPolicy AI Agent...")
        if enterprise_id:
            print(f"[*] 目标企业: {enterprise_id}")
        print(f"[*] 任务输入: {prompt[:80]}...")

        # 1. 组装系统 Prompt
        system_prompt = self._build_system_prompt(enterprise_id)
        
        # 2. 初始化对话历史
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # 3. ReAct 循环
        for turn in range(1, max_turns + 1):
            print(f"\n[轮次 {turn}/{max_turns}] 正在思考中...")
            
            try:
                response = self.llm.chat_completion(
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                    temperature=0.2
                )
            except Exception as e:
                err_msg = f"大模型 API 访问失败: {e}"
                print(f"[!] {err_msg}")
                return err_msg

            choice = response.choices[0]
            message = choice.message
            
            # 将模型的回答加入上下文（包含可能存在的 tool_calls）
            # 注意: 某些 OpenAI 兼容接口可能要求我们将 message 对象直接或者转换后存入
            message_dict = {
                "role": "assistant",
                "content": message.content or ""
            }
            if getattr(message, "tool_calls", None):
                message_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            
            messages.append(message_dict)

            # 输出模型思考过程
            if message.content:
                print(f"\n[Agent 思考]\n{message.content}")

            # 检查是否需要调用工具
            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                print("\n[OK] Agent 决策完毕，已输出最终结论。")
                return message.content or ""

            # 依次执行工具调用
            for tool_call in tool_calls:
                name = tool_call.function.name
                args_str = tool_call.function.arguments
                
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {}
                    
                print(f"\n[Action] -> 调用工具: {name}")
                print(f"         -> 参数: {json.dumps(args, ensure_ascii=False)}")
                
                # 执行具体工具
                observation = execute_tool(name, args)
                obs_str = json.dumps(observation, ensure_ascii=False)
                
                # 打印 Observation 摘要，防止屏幕被大文本刷屏
                summary_obs = obs_str[:200] + "..." if len(obs_str) > 200 else obs_str
                print(f"[Observation] -> 返回结果: {summary_obs}")
                
                # 将观察结果（Observation）加入消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": obs_str
                })

        print(f"\n[!] 达到最大轮次限制 ({max_turns})，终止 ReAct 循环。")
        # 兜底返回模型最后一次的输出
        return messages[-1].get("content", "Agent 未能完成分析规划。")

    def _build_system_prompt(self, enterprise_id: Optional[str]) -> str:
        """构建详细的系统提示词"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        prompt = f"""# 角色
你是一个极其专业的“经济政策分析专家系统”核心 AI Agent 智能体。
当前时间: {now_str}

## 任务目标
你的任务是为企业进行深入、量化的经济政策匹配分析，提供科学、客观的申报与应对决策，并生成高标准的政策分析报告。

## 核心计算准则 — 严禁数字幻觉
你是一个“智能体控制中心”，而不是纯文本生成器。
1. 所有关于匹配评分（四维分数、成功概率）、ROI财务指标（预期收益、合规成本、回本周期）、组合叠加（收入天花板、最优方案）的数据，**必须来自于工具调用**！
2. 绝对不能自己主观捏造任何匹配分、成功概率、ROI数字。
3. 当你得到工具返回的计算结果后，你应该将这些数据无缝缝合到你的最终分析报告中。

## 标准分析工作流 (六步法)
如果你被要求分析某项新政策对企业的适配性，请严格遵循以下工作流程：
1. **政策录入与结构化**：抓取政策 URL (通过 `fetch_policy_url`) 或解析本地文件 (通过 `parse_policy_file`)，提取出政策标题、发布日期、发布来源和核心内容。
2. **画像匹配打分**：调用 `match_enterprise_policy` 获取四维匹配得分（Tech、Prod、Mkt、Cap）、硬性条件判定及成功概率。
3. **财务 ROI 计算**：如果匹配度合适，调用 `calculate_policy_roi` 基于成功概率和政策分类估算申报 ROI、申报成本和回报周期。
4. **组合叠加分析（多政策时）**：如果有多个政策同时考虑，调用 `optimize_policy_stacking` 评估互斥性，计算收入天花板，获得最优组合建议。
5. **深度报告生成**：编写完整的分析报告，结构与内容需完美符合下方输出规范。
6. **保存报告**：调用 `write_markdown_report` 将你的最终报告保存为 .md 文件至企业工作区。

## 输出格式规范（遵守 config/output_standards.md）
你生成的所有 Markdown 报告必须严格遵守以下排版原则，否则视为失败：
1. **YAML Frontmatter 元数据**：每个报告文件头部必须包含 YAML frontmatter (包含 title, date, author, status, tags 字段)。
2. **一句话判断**：在标题下方第一个元素，使用引用块 `> **一句话判断**：[30字内的核心结论]`。
3. **禁用符号**：禁用 emoji 表情（例如 、✅ 等），禁用 unicode 框线符号，禁用 '<=' 或 '>='（改用文字'不大于/不小于'或'<= / >='），禁用 '->'（改用 ASCII 文字描述或'➔'）。
4. **表格与分隔线**：大章节之间使用 `---` 分隔线。表格列数不能超过 5 列。
5. **Callout 标注**：使用 GitHub/Obsidian 风格的 Callout 标注重要或风险信息，如 `> [!IMPORTANT]`、`> [!WARNING]`、`> [!TIP]`。
6. **企业工作区路径**：生成的报告请规范保存在 enterprises/{{enterprise_id}}/workspace/ 下，文件名格式如 `policy_analysis_YYYY-MM-DD_描述.md`。

"""

        if enterprise_id:
            enterprise_context = self._load_enterprise_context(enterprise_id)
            prompt += f"""
## 当前分析企业上下文
你正在为企业 ID 为 **{enterprise_id}** 的企业服务。以下是该企业的详细画像与配置：

{enterprise_context}
"""
        else:
            prompt += """
## 注意
当前未指定具体的企业 ID。如果用户需要针对特定企业进行匹配或计算，你可以通过工具列表查询可用企业，或引导用户提供企业 ID。
"""

        return prompt
