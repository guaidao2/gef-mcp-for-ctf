"""
GEF MCP 工具函数：ANSI 清理、输入消杀、日志配置

玄幕安全团队 - guaidao2 开发
"""

import os
import re
import logging
from typing import Optional

# ── ANSI / 控制字符清理 ─────────────────────────────────────────

ANSI_ESCAPE_PATTERN = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
ANSI_ESCAPE_EXTENDED = re.compile(r'\x1b\][^\x07]*\x07')
ANSI_ESCAPE_OTHER = re.compile(r'\x1b\[^[A-Z@]')
CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

# ⚠️ 允许通过 execute_command 的 GDB 特殊前缀 —— 用户显式要求运行任意命令时放行
# 但禁止在文件路径/搜索模式中使用
SHELL_ESCAPE_CHARS = re.compile(r'[!;|&`$(){}[\]<>#]')
NEWLINE_CHARS = re.compile(r'[\r\n]')

# 输出大小硬限制 (50KB)
MAX_OUTPUT_SIZE = 50 * 1024


def clean_output(output: str, max_size: int = MAX_OUTPUT_SIZE) -> str:
    """清理 GDB/GEF 输出中的 ANSI 转义序列和控制字符"""
    if not output:
        return ""

    # 截断过大的输出
    if len(output) > max_size:
        output = output[:max_size] + "\n\n[Output truncated at {} bytes]".format(max_size)

    cleaned = ANSI_ESCAPE_PATTERN.sub('', output)
    cleaned = ANSI_ESCAPE_EXTENDED.sub('', cleaned)
    cleaned = ANSI_ESCAPE_OTHER.sub('', cleaned)
    cleaned = CONTROL_CHARS.sub('', cleaned)
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')

    lines = [line.rstrip() for line in cleaned.split('\n')]
    # 删除末尾空行
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


# ── 输入消杀 ────────────────────────────────────────────────────

def sanitize_filepath(filepath: str) -> str:
    """消杀文件路径，阻止通过 PTY 注入 GDB 命令或 Shell 命令

    Raises:
        ValueError: 路径包含非法字符
    """
    if not filepath or not filepath.strip():
        raise ValueError("Filepath must not be empty")

    if NEWLINE_CHARS.search(filepath):
        raise ValueError("Filepath must not contain newline characters")

    if SHELL_ESCAPE_CHARS.search(filepath):
        raise ValueError(
            "Filepath contains shell metacharacters which are not allowed: "
            "! ; | & ` $ ( ) { } [ ] < > #"
        )

    if filepath.startswith('-'):
        raise ValueError(f"Filepath must not start with dash: {filepath}")

    # 规范化路径 (移除 .. 等)
    normalized = os.path.normpath(filepath)

    return normalized


def sanitize_pattern(pattern: str) -> str:
    """消杀搜索模式 —— 允许十六进制和正常字符串，阻止换行注入"""
    if not pattern or not pattern.strip():
        raise ValueError("Pattern must not be empty")

    if NEWLINE_CHARS.search(pattern):
        raise ValueError("Pattern must not contain newline characters")

    # 十六进制模式允许 \x 前缀
    # 允许常见的安全测试模式: /bin/sh, flag, 0xdeadbeef
    return pattern


def sanitize_location(location: str) -> str:
    """消杀断点/反汇编位置参数"""
    if not location or not location.strip():
        raise ValueError("Location must not be empty")

    if NEWLINE_CHARS.search(location):
        raise ValueError("Location must not contain newline characters")

    # GDB 位置语法允许: function, *address, file:line, +offset
    # 这些都是合法的调试语法，不做额外限制
    return location


# ── 日志配置 ────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger("gef-mcp")

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 避免重复添加 handler
    if not logger.handlers:
        logger.setLevel(numeric_level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)-7s %(name)s - %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
    else:
        logger.setLevel(numeric_level)

    return logger


# 全局 logger 实例
log: logging.Logger = setup_logging()
