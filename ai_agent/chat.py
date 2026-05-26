# -*- coding: utf-8 -*-
"""
EcoPolicy AI Agent CLI Dialogue Interface
Provides interactive terminal multi-turn dialogue loop.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_agent.llm import LLMClient
from ai_agent.analyst import PolicyAnalystAgent
from enterprise_matcher import EnterpriseMatcher


def list_available_enterprises() -> list:
    """获取并列出所有可用企业"""
    try:
        matcher = EnterpriseMatcher(str(BASE_DIR / "enterprises"))
        return matcher.get_enterprise_ids()
    except Exception as e:
        print(f"[!] 加载企业画像目录失败: {e}")
        return []


def start_chat_session(default_enterprise_id: Optional[str] = None):
    """启动交互式智能体对话"""
    print("=" * 60)
    print("       经济政策分析 AI Agent 交互终端 (EcoPolicy Agent)")
    print("=" * 60)
    
    # 1. 检查 LLM 可用性
    llm = LLMClient()
    if not llm.is_available():
        print("[!] 错误: 未检测到 API Key，请先配置环境变量。")
        print("    可在终端中执行:")
        print("      $env:ECOPOLICY_API_KEY=\"你的API-KEY\"  (PowerShell)")
        print("      set ECOPOLICY_API_KEY=你的API-KEY     (CMD)")
        print("    或配置 ECOPOLICY_BASE_URL (例如: https://api.deepseek.com)")
        print("=" * 60)
        return

    # 2. 选择企业 ID
    enterprise_ids = list_available_enterprises()
    current_enterprise = default_enterprise_id

    if not current_enterprise:
        if len(enterprise_ids) == 1:
            current_enterprise = enterprise_ids[0]
            print(f"[*] 自动选择唯一可用企业: {current_enterprise}")
        elif len(enterprise_ids) > 1:
            print("\n发现以下企业画像，请输入序号选择目标企业:")
            for idx, eid in enumerate(enterprise_ids, 1):
                print(f"  [{idx}] {eid}")
            
            while True:
                choice = input("\n请选择企业序号 (回车默认为 1): ").strip()
                if not choice:
                    current_enterprise = enterprise_ids[0]
                    break
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(enterprise_ids):
                        current_enterprise = enterprise_ids[idx - 1]
                        break
                    else:
                        print("[!] 序号超出范围，请重新输入")
                except ValueError:
                    print("[!] 输入无效，请确认是数字序号")
        else:
            print("[!] 警告: 未在 enterprises 目录下找到任何企业画像文件夹。")
            print("    智能体将在无企业上下文状态下运行。部分匹配及计算工具可能报错。")

    print(f"\n[*] 当前服务企业: {current_enterprise or '无'}")
    print("[*] 提示: 你可以直接向智能体提问，或者让它执行特定分析任务。")
    print("    常用指令:")
    print("      /exit             - 退出对话")
    print("      /enterprise <ID>  - 切换服务企业")
    print("      /list             - 列出可用企业画像")
    print("      /help             - 显示此帮助")
    print("-" * 60)

    agent = PolicyAnalystAgent(llm)

    # 3. 循环交互
    while True:
        try:
            prompt_str = f"EcoPolicy Agent ({current_enterprise or '无'}) > "
            user_input = input(prompt_str).strip()
            
            if not user_input:
                continue
                
            # 处理斜杠指令
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0].lower()
                
                if cmd == "/exit" or cmd == "/quit":
                    print("\n[*] 感谢使用 EcoPolicy Agent，再见！")
                    break
                    
                elif cmd == "/list":
                    eids = list_available_enterprises()
                    print(f"\n可用企业列表: {', '.join(eids)}")
                    continue
                    
                elif cmd == "/enterprise":
                    if len(parts) < 2:
                        print("[!] 请指定企业 ID，例如: /enterprise jyuh")
                        continue
                    new_id = parts[1]
                    eids = list_available_enterprises()
                    if new_id not in eids:
                        print(f"[!] 警告: 未在画像库中找到 '{new_id}'。")
                        confirm = input(f"    是否强制切换至 '{new_id}'? (y/n, 默认 n): ").strip().lower()
                        if confirm != 'y':
                            continue
                    current_enterprise = new_id
                    agent = PolicyAnalystAgent(llm)  # 重新创建以重置上下文
                    print(f"[*] 已切换服务企业为: {current_enterprise}")
                    continue
                    
                elif cmd == "/help":
                    print("\n系统指令:")
                    print("  /exit             - 退出对话")
                    print("  /enterprise <ID>  - 切换服务企业")
                    print("  /list             - 列出可用企业画像")
                    print("  /help             - 显示此帮助")
                    continue
                    
                else:
                    print(f"[!] 未知指令 '{cmd}'，输入 /help 查看帮助。")
                    continue

            # 调用智能体
            response = agent.run(user_input, enterprise_id=current_enterprise)
            
            print("\n" + "=" * 60)
            print("[Agent 最终答复]\n")
            print(response)
            print("=" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n[*] 感谢使用 EcoPolicy Agent，再见！")
            break
        except Exception as e:
            print(f"\n[!] 发生未知错误: {e}\n")


if __name__ == "__main__":
    start_chat_session()
