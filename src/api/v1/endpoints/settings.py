from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import logging
from pathlib import Path

# 设置.env文件的路径
env_path = Path(__file__).parent.parent.parent.parent.parent / ".env"

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    responses={404: {"description": "Not found"}}
)

class SettingUpdateRequest(BaseModel):
    key: str
    value: str

class SettingUpdateResponse(BaseModel):
    success: bool
    message: str
    old_value: Optional[str] = None
    failed_keys: Optional[list[str]] = None

class SettingsResponse(BaseModel):
    settings: Dict[str, str]

class BatchUpdateRequest(BaseModel):
    settings: Dict[str, str]


def get_env() -> tuple[bool, str, Optional[Dict[str, str]]]:
    """读取.env文件中的所有环境变量"""

    if not env_path.exists():
        return False, f".env文件不存在于目录{env_path}", None

    try:
        env_vars = {}

        with open(env_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue

                # 检查是否包含等号
                if '=' not in line:
                    logger.warning(f"第{line_num}行格式不正确，跳过: {line}")
                    continue

                # 分割键值对
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # 移除值两端的引号（如果存在）
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value

        return True, f"成功读取{len(env_vars)}个环境变量", env_vars

    except Exception as e:
        logger.error(f"读取环境变量失败: {str(e)}")
        return False, f"读取失败: {str(e)}", None

def update_env(key: str, value: str) -> tuple[bool, str, Optional[str]]:
    """更新.env文件中的环境变量"""

    if not env_path.exists():
        return False, f".env文件不存在于目录{env_path}", None

    try:
        # 读取现有内容
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 查找并更新变量
        updated = False
        old_value = None
        new_lines = []

        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                if '=' in line and line.split('=')[0].strip() == key:
                    old_value = line.split('=', 1)[1].strip()
                    new_lines.append(f"{key}={value}\n")
                    updated = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # 如果变量不存在，添加新变量
        if not updated:
            new_lines.append(f"{key}={value}\n")

        # 写回文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 更新运行时环境变量
        os.environ[key] = value

        return True, f"环境变量{key}更新成功", old_value

    except Exception as e:
        logger.error(f"更新环境变量失败: {str(e)}")
        return False, f"更新失败: {str(e)}", None


@router.get("/", response_model=SettingsResponse)
async def get_settings():
    """获取当前环境变量配置"""
    success, message, env_vars = get_env()

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )

    logger.info(f"成功获取环境变量")
    return SettingsResponse(settings=env_vars)


@router.put("/", response_model=SettingUpdateResponse)
async def update_setting(request: SettingUpdateRequest):
    """更新单个环境变量"""
    if request.key != request.key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="路径参数与请求体中的key不匹配"
        )

    success, message, old_value = update_env(request.key, request.value)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message
        )

    logger.info(f"环境变量 {request.key} 已更新: {old_value} -> {request.value}")

    return SettingUpdateResponse(
        success=True,
        message=message,
        old_value=old_value
    )


@router.put("/batch", response_model=SettingUpdateResponse)
async def update_settings_batch(request: BatchUpdateRequest):
    """批量更新环境变量"""
    try:
        updated_count = 0
        failed = []
        for key, value in request.settings.items():
            success, _, _ = update_env(key, value)
            if success:
                updated_count += 1
            else:
                failed.append(key)

        logger.info(f"批量更新完成，成功更新 {updated_count} 个环境变量")

        return SettingUpdateResponse(
            success=True,
            message=f"成功更新 {updated_count} 个环境变量" if updated_count > 0 else "没有更新任何环境变量",
            failed_keys=failed if failed else None
        )

    except Exception as e:
        logger.error(f"批量更新失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新失败: {str(e)}"
        )
