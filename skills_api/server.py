# -*- coding: utf-8 -*-
"""
FastAPI Server for EcoPolicy-AI Skills
Exposes policy matching, crawling, ROI estimation, and stacking optimization as REST API services.
"""

import os
import sys
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Ensure project root is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Import tools functions for consistency
from ai_agent.tools import (
    fetch_policy_url,
    parse_policy_file,
    match_enterprise_policy,
    calculate_policy_roi,
    optimize_policy_stacking,
    write_markdown_report,
    save_enterprise_profile,
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ecopolicy.skills.server")

# Initialize FastAPI App
app = FastAPI(
    title="EcoPolicy-AI Skills API",
    description="将经济政策抓取、匹配、评估、堆叠规划能力包装为标准 API 技能工具箱",
    version="1.0.0"
)


# ============================================================
# Pydantic Schemas for Requests
# ============================================================

class FetchUrlRequest(BaseModel):
    url: str = Field(..., description="要抓取解析的政策网页 URL 链接")


class ParseFileRequest(BaseModel):
    file_path: str = Field(..., description="本地服务器上的政策文档文件相对/绝对路径")


class MatchRequest(BaseModel):
    enterprise_id: str = Field(..., description="企业 ID，如 'jyuh'")
    policy_title: str = Field(..., description="政策标题")
    policy_summary: str = Field(..., description="政策摘要或内容")
    policy_url: Optional[str] = Field("", description="可选。政策网页链接")


class CalculateROIRequest(BaseModel):
    enterprise_id: str = Field(..., description="企业 ID，如 'jyuh'")
    policy_title: str = Field(..., description="政策标题")
    policy_summary: str = Field(..., description="政策摘要或内容")
    success_probability: float = Field(..., ge=0.0, le=1.0, description="申报成功概率（0.0 至 1.0）")


class StackingPolicyInput(BaseModel):
    title: str = Field(..., description="政策标题")
    summary: str = Field(..., description="政策摘要或内容")
    url: Optional[str] = Field("", description="可选。政策链接")
    success_probability: Optional[float] = Field(None, description="可选。申报成功概率")
    recommendation_score: Optional[int] = Field(None, description="可选。推荐等级分数")


class StackingRequest(BaseModel):
    enterprise_id: str = Field(..., description="企业 ID，如 'jyuh'")
    policies: List[StackingPolicyInput] = Field(..., description="要进行叠加优化组合分析的政策列表")


class WriteReportRequest(BaseModel):
    enterprise_id: str = Field(..., description="企业 ID，如 'jyuh'")
    filename: str = Field(..., description="保存的文件名，如 'policy_analysis_report.md'")
    markdown_content: str = Field(..., description="完整的 Markdown 报告文本内容")


class SaveProfileRequest(BaseModel):
    enterprise_id: str = Field(..., description="企业 ID，例如 'tencent'")
    profile_yaml: str = Field(..., description="格式完备的 YAML 企业画像内容")


# ============================================================
# Endpoints
# ============================================================

@app.get("/")
def read_root():
    return {
        "message": "欢迎使用 EcoPolicy-AI Skills API!",
        "version": "1.0.0",
        "swagger_docs": "/docs",
        "openapi_spec": "/openapi.json"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/skills/fetch_url", summary="网页政策抓取技能")
def api_fetch_url(request: FetchUrlRequest):
    result = fetch_policy_url(request.url)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/parse_file", summary="本地政策文件解析技能")
def api_parse_file(request: ParseFileRequest):
    result = parse_policy_file(request.file_path)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/upload_file", summary="HTTP 文件上传并解析技能")
def api_upload_file(file: UploadFile = File(...)):
    """上传文件并解析（支持 PDF、Word、TXT），常用于 Dify/Coze 平台用户直接上传附件"""
    temp_dir = BASE_DIR / "policy_data" / "temp_uploads"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Secure filename
    clean_filename = os.path.basename(file.filename)
    filepath = temp_dir / clean_filename
    
    try:
        with open(filepath, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        result = parse_policy_file(str(filepath))
        
        # Cleanup temp file after parsing
        if filepath.exists():
            os.remove(filepath)
            
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
            
        return result
    except Exception as e:
        if filepath.exists():
            os.remove(filepath)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/skills/match", summary="企业-政策匹配评估技能")
def api_match(request: MatchRequest):
    result = match_enterprise_policy(
        enterprise_id=request.enterprise_id,
        policy_title=request.policy_title,
        policy_summary=request.policy_summary,
        policy_url=request.policy_url
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/calculate_roi", summary="政策申报财务 ROI 测算技能")
def api_calculate_roi(request: CalculateROIRequest):
    result = calculate_policy_roi(
        enterprise_id=request.enterprise_id,
        policy_title=request.policy_title,
        policy_summary=request.policy_summary,
        success_probability=request.success_probability
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/optimize_stacking", summary="多政策互斥与组合叠加规划技能")
def api_optimize_stacking(request: StackingRequest):
    # Convert Pydantic model items to raw dicts for optimize_policy_stacking function
    policies_dict_list = []
    for p in request.policies:
        policies_dict_list.append(p.model_dump())
        
    result = optimize_policy_stacking(
        enterprise_id=request.enterprise_id,
        policies=policies_dict_list
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/write_report", summary="Markdown 分析报告生成与工作区保存技能")
def api_write_report(request: WriteReportRequest):
    result = write_markdown_report(
        enterprise_id=request.enterprise_id,
        filename=request.filename,
        markdown_content=request.markdown_content
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@app.post("/api/skills/save_profile", summary="保存或更新企业画像技能")
def api_save_profile(request: SaveProfileRequest):
    result = save_enterprise_profile(
        enterprise_id=request.enterprise_id,
        profile_yaml=request.profile_yaml
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
