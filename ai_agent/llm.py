# -*- coding: utf-8 -*-
"""
LLM Client Wrapper for EcoPolicy AI Agent
Supports OpenAI-compatible APIs (DeepSeek, OpenAI, SiliconFlow, Ollama, etc.)
"""

import os
import logging
from typing import List, Dict, Any, Generator

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger("ecopolicy.agent.llm")


class LLMClient:
    """封装大模型 API 客户端"""

    def __init__(self):
        # 1. 尝试获取 API Key，支持多种环境变量
        self.api_key = os.environ.get("ECOPOLICY_API_KEY") or \
                       os.environ.get("DEEPSEEK_API_KEY") or \
                       os.environ.get("OPENAI_API_KEY")

        # 2. 尝试获取 Base URL，默认指向 DeepSeek 官方
        self.base_url = os.environ.get("ECOPOLICY_BASE_URL") or \
                        os.environ.get("DEEPSEEK_BASE_URL") or \
                        os.environ.get("OPENAI_BASE_URL") or \
                        "https://api.deepseek.com"

        # 3. 尝试获取模型名称，默认使用 deepseek-chat (DeepSeek-V3)
        self.model = os.environ.get("ECOPOLICY_MODEL") or \
                     os.environ.get("DEEPSEEK_MODEL") or \
                     os.environ.get("OPENAI_MODEL") or \
                     "deepseek-chat"

        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        if not self.api_key:
            logger.warning("未配置 API Key (ECOPOLICY_API_KEY/DEEPSEEK_API_KEY/OPENAI_API_KEY)")
            return

        if OpenAI is None:
            logger.error("未安装 openai 库，请先执行 pip install openai")
            return

        try:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            logger.info(f"LLM 客户端初始化成功: Model={self.model}, BaseURL={self.base_url}")
        except Exception as e:
            logger.error(f"LLM 客户端初始化失败: {e}")

    def is_available(self) -> bool:
        """检查客户端是否可用"""
        return self.client is not None

    def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.2,
        response_format: Dict[str, Any] = None,
        tools: List[Dict[str, Any]] = None
    ) -> Any:
        """执行标准非流式对话"""
        if not self.is_available():
            raise RuntimeError("LLM 客户端不可用，请检查 API Key 配置与 openai 库安装")

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.chat.completions.create(**kwargs)
            return response
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise e

    def chat_completion_stream(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.2
    ) -> Generator[str, None, None]:
        """执行流式对话，返回生成器"""
        if not self.is_available():
            raise RuntimeError("LLM 客户端不可用，请检查 API Key 配置与 openai 库安装")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"LLM 流式调用失败: {e}")
            raise e
