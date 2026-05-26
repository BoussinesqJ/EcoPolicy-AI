# -*- coding: utf-8 -*-
"""
Export OpenAPI JSON schema for EcoPolicy-AI Skills
Generates skills_openapi.json at the project root for integration with Dify / Coze.
"""

import os
import sys
import json
from pathlib import Path

# Ensure project root is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from skills_api.server import app
from fastapi.openapi.utils import get_openapi


def export_schema():
    """导出 OpenAPI 规范的 JSON 文件"""
    print("[*] 正在导出 EcoPolicy-AI Skills OpenAPI Schema...")
    
    # 获取 OpenAPI 字典
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # 定义输出文件路径
    output_path = BASE_DIR / "skills_openapi.json"
    
    # 写入 JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"[OK] 导出成功！保存路径: {output_path}")
    print("    您可以直接将该 json 文件上传至 Dify, Coze, GPTs 等平台作为外部自定义工具使用。")


if __name__ == "__main__":
    export_schema()
