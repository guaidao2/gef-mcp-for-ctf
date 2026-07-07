"""
GEF MCP 工具定义与回调处理

玄幕安全团队 - guaidao2 开发
"""

import functools
from typing import Dict, Any

from mcp.types import Tool

from manager import session_manager
from utils import sanitize_location, log


# ══════════════════════════════════════════════════════════════════
# 装饰器：消除重复的 session 校验样板
# ══════════════════════════════════════════════════════════════════

def require_session(func):
    """装饰器：自动校验 session_id 和会话活跃状态

    被装饰函数的第一个参数接收 GefSession 实例。
    """

    @functools.wraps(func)
    def wrapper(params: dict, *args, **kwargs):
        session_id = params.get("session_id")
        if not session_id:
            return {"success": False, "error": "session_id is required"}
        session = session_manager.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": f"Session {session_id} not found. "
                         f"Use create_session first.",
            }
        if not session.is_alive():
            return {
                "success": False,
                "error": f"Session {session_id} is not active. "
                         f"Create a new session.",
            }
        try:
            return func(params, session, *args, **kwargs)
        except ValueError as e:
            return {"success": False, "error": str(e)}

    return wrapper


# ══════════════════════════════════════════════════════════════════
# 工具回调函数
# ══════════════════════════════════════════════════════════════════

# ── 会话管理 ────────────────────────────────────────────────────

def create_session_tool(params: dict) -> dict:
    timeout = params.get("timeout", 10)
    return session_manager.create_session(timeout=timeout)


def list_sessions_tool(params: dict) -> dict:
    return session_manager.list_sessions()


def close_session_tool(params: dict) -> dict:
    session_id = params.get("session_id")
    if not session_id:
        return {"success": False, "error": "session_id is required"}
    return session_manager.close_session(session_id)


# ── 文件操作 ────────────────────────────────────────────────────

@require_session
def load_file_tool(params: dict, session) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        return {"success": False, "error": "filepath is required"}
    result = session.load_file(filepath)
    return {"success": True, "output": result}


@require_session
def start_debugging_tool(params: dict, session) -> dict:
    filepath = params.get("filepath")
    if not filepath:
        return {"success": False, "error": "filepath is required"}
    result = session.start_debugging(filepath)
    return {"success": True, "output": result}


# ── 通用命令 ────────────────────────────────────────────────────

@require_session
def execute_command_tool(params: dict, session) -> dict:
    command = params.get("command")
    if not command:
        return {"success": False, "error": "command is required"}

    # ⚠️ 用户显式选择运行任意命令 —— 不去消杀，但记录日志
    log.info("Session %s: execute_command: %s", session.session_id,
             command[:200])
    result = session.execute_gef_command(command)
    return {"success": True, "output": result}


# ── 断点 ────────────────────────────────────────────────────────

@require_session
def set_breakpoint_tool(params: dict, session) -> dict:
    location = params.get("location")
    if not location:
        return {"success": False, "error": "location is required"}
    location = sanitize_location(location)
    result = session.set_breakpoint(location)
    return {"success": True, "output": result}


@require_session
def delete_breakpoint_tool(params: dict, session) -> dict:
    number = params.get("number")
    if number is None:
        return {"success": False, "error": "number is required"}
    try:
        number = int(number)
    except (TypeError, ValueError):
        return {"success": False, "error": "number must be an integer"}
    result = session.delete_breakpoint(number)
    return {"success": True, "output": result}


@require_session
def list_breakpoints_tool(params: dict, session) -> dict:
    result = session.list_breakpoints()
    return {"success": True, "output": result}


@require_session
def watchpoint_tool(params: dict, session) -> dict:
    address = params.get("address")
    kind = params.get("kind", "write")
    if not address:
        return {"success": False, "error": "address is required"}
    if kind not in ("write", "read", "access"):
        return {"success": False, "error": "kind must be write/read/access"}
    result = session.set_watchpoint(address, kind)
    return {"success": True, "output": result}


# ── 执行控制 ────────────────────────────────────────────────────

@require_session
def run_tool(params: dict, session) -> dict:
    args = params.get("args", "")
    result = session.run(args)
    return {"success": True, "output": result}


@require_session
def continue_tool(params: dict, session) -> dict:
    result = session.continue_execution()
    return {"success": True, "output": result}


@require_session
def step_tool(params: dict, session) -> dict:
    result = session.step()
    return {"success": True, "output": result}


@require_session
def next_tool(params: dict, session) -> dict:
    result = session.next()
    return {"success": True, "output": result}


# ── 寄存器 / 栈 / 反汇编 ────────────────────────────────────────

@require_session
def get_registers_tool(params: dict, session) -> dict:
    result = session.get_registers()
    return {"success": True, "output": result}


@require_session
def get_backtrace_tool(params: dict, session) -> dict:
    result = session.get_backtrace()
    return {"success": True, "output": result}


@require_session
def info_frame_tool(params: dict, session) -> dict:
    result = session.info_frame()
    return {"success": True, "output": result}


@require_session
def disassemble_tool(params: dict, session) -> dict:
    location = params.get("location")
    count = params.get("count", 10)
    result = session.disassemble(location, count)
    return {"success": True, "output": result}


# ── 内存 ────────────────────────────────────────────────────────

@require_session
def examine_memory_tool(params: dict, session) -> dict:
    address = params.get("address")
    count = params.get("count", 16)
    if not address:
        return {"success": False, "error": "address is required"}
    result = session.examine_memory(address, count)
    return {"success": True, "output": result}


@require_session
def write_memory_tool(params: dict, session) -> dict:
    address = params.get("address")
    value = params.get("value")
    size = params.get("size", "int")
    if not address or value is None:
        return {"success": False, "error": "address and value are required"}
    result = session.write_memory(address, value, size)
    return {"success": True, "output": result}


@require_session
def patch_byte_tool(params: dict, session) -> dict:
    address = params.get("address")
    byte_str = params.get("bytes")
    if not address or not byte_str:
        return {"success": False, "error": "address and bytes are required"}
    result = session.patch_byte(address, byte_str)
    return {"success": True, "output": result}


@require_session
def hexdump_tool(params: dict, session) -> dict:
    address = params.get("address")
    count = params.get("count", 64)
    if not address:
        return {"success": False, "error": "address is required"}
    result = session.hexdump(address, count)
    return {"success": True, "output": result}


@require_session
def telescope_tool(params: dict, session) -> dict:
    address = params.get("address")
    count = params.get("count", 10)
    if not address:
        return {"success": False, "error": "address is required"}
    result = session.telescope(address, count)
    return {"success": True, "output": result}


@require_session
def search_pattern_tool(params: dict, session) -> dict:
    pattern = params.get("pattern")
    if not pattern:
        return {"success": False, "error": "pattern is required"}
    result = session.search_pattern(pattern)
    return {"success": True, "output": result}


@require_session
def search_strings_tool(params: dict, session) -> dict:
    pattern = params.get("pattern", "")
    result = session.search_strings(pattern)
    return {"success": True, "output": result}


# ── GEF 特色命令 ────────────────────────────────────────────────

@require_session
def vmmap_tool(params: dict, session) -> dict:
    result = session.vmmap()
    return {"success": True, "output": result}


@require_session
def heap_tool(params: dict, session) -> dict:
    result = session.heap()
    return {"success": True, "output": result}


@require_session
def checksec_tool(params: dict, session) -> dict:
    result = session.checksec()
    return {"success": True, "output": result}


@require_session
def got_plt_tool(params: dict, session) -> dict:
    result = session.got_plt()
    return {"success": True, "output": result}


@require_session
def get_context_tool(params: dict, session) -> dict:
    result = session.get_context()
    return {"success": True, "output": result}


@require_session
def get_sections_tool(params: dict, session) -> dict:
    result = session.get_sections()
    return {"success": True, "output": result}


@require_session
def get_entry_point_tool(params: dict, session) -> dict:
    result = session.get_entry_point()
    return {"success": True, "output": result}


@require_session
def elf_info_tool(params: dict, session) -> dict:
    result = session.get_elf_info()
    return {"success": True, "output": result}


@require_session
def reset_cache_tool(params: dict, session) -> dict:
    result = session.reset_cache()
    return {"success": True, "output": result}


# ── CTF 高级工具 ────────────────────────────────────────────────

@require_session
def rop_search_tool(params: dict, session) -> dict:
    gadget = params.get("gadget", "")
    result = session.rop_search(gadget)
    return {"success": True, "output": result}


@require_session
def rop_search_all_tool(params: dict, session) -> dict:
    result = session.rop_search_all()
    return {"success": True, "output": result}


@require_session
def attach_process_tool(params: dict, session) -> dict:
    pid = params.get("pid")
    if pid is None:
        return {"success": False, "error": "pid is required"}
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return {"success": False, "error": "pid must be an integer"}
    result = session.attach_process(pid)
    return {"success": True, "output": result}


@require_session
def detach_process_tool(params: dict, session) -> dict:
    result = session.detach_process()
    return {"success": True, "output": result}


@require_session
def format_string_helper_tool(params: dict, session) -> dict:
    result = session.format_string_helper()
    return {"success": True, "output": result}


@require_session
def assemble_tool(params: dict, session) -> dict:
    address = params.get("address")
    instruction = params.get("instruction")
    if not address or not instruction:
        return {"success": False, "error": "address and instruction are required"}
    result = session.assemble(address, instruction)
    return {"success": True, "output": result}


@require_session
def nop_sled_tool(params: dict, session) -> dict:
    address = params.get("address")
    count = params.get("count", 16)
    if not address:
        return {"success": False, "error": "address is required"}
    result = session.nop_sled(address, count)
    return {"success": True, "output": result}


# ══════════════════════════════════════════════════════════════════
# 工具表 (Tool 定义)
# ══════════════════════════════════════════════════════════════════

TOOLS: list[Tool] = [
    # ── 会话管理 ──
    Tool(
        name="create_session",
        description="""创建新的 GEF 调试会话。

自动加载 GEF 插件，初始化 GDB 环境。
最多支持 4 个并发会话。

Args:
    timeout: 命令执行超时时间(秒)，默认 10

Returns:
    session_id: 会话 ID，用于后续操作
""",
        inputSchema={
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "integer",
                    "description": "命令执行超时时间(秒)",
                    "default": 10,
                }
            },
        },
    ),
    Tool(
        name="list_sessions",
        description="列出所有活跃的 GEF 会话。",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="close_session",
        description="""关闭 GEF 会话并释放资源。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),

    # ── 文件操作 ──
    Tool(
        name="load_file",
        description="""加载目标二进制文件到 GEF 会话。

Args:
    session_id: 会话 ID
    filepath: 文件路径
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "filepath": {"type": "string", "description": "目标文件路径"},
            },
            "required": ["session_id", "filepath"],
        },
    ),
    Tool(
        name="start_debugging",
        description="""加载目标文件并显示 GEF 调试上下文 (类似 `gef <文件>` 命令)。

Args:
    session_id: 会话 ID
    filepath: 文件路径

Example:
    start_debugging({"session_id": "abc123", "filepath": "/path/to/binary"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "filepath": {"type": "string", "description": "目标文件路径"},
            },
            "required": ["session_id", "filepath"],
        },
    ),

    # ── 通用命令 ──
    Tool(
        name="execute_command",
        description="""执行任意 GEF/GDB 命令。

支持所有 GEF 增强命令和 GDB 原生命令，包括但不限于：
- GEF: vmmap, heap, telescope, search-pattern, checksec, got, rop
- GDB: info, break, set, examine, step, next, continue

Args:
    session_id: 会话 ID
    command: 要执行的 GEF/GDB 命令

⚠️ 此工具直接执行任意命令，请确保命令来源可信。
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "command": {"type": "string", "description": "GEF/GDB 命令"},
            },
            "required": ["session_id", "command"],
        },
    ),

    # ── 断点 ──
    Tool(
        name="set_breakpoint",
        description="""设置断点。

Args:
    session_id: 会话 ID
    location: 断点位置 (函数名、地址、文件名:行号等)

Examples:
    set_breakpoint({"session_id": "abc", "location": "main"})
    set_breakpoint({"session_id": "abc", "location": "*0x401000"})
    set_breakpoint({"session_id": "abc", "location": "vuln.c:42"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "location": {"type": "string", "description": "断点位置"},
            },
            "required": ["session_id", "location"],
        },
    ),
    Tool(
        name="delete_breakpoint",
        description="""按编号删除断点或监视点。

Args:
    session_id: 会话 ID
    number: 断点编号 (可用 list_breakpoints 查看)
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "number": {"type": "integer", "description": "断点编号"},
            },
            "required": ["session_id", "number"],
        },
    ),
    Tool(
        name="list_breakpoints",
        description="""列出所有断点和监视点。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="watchpoint",
        description="""设置数据断点 (监视点)。

Args:
    session_id: 会话 ID
    address: 要监视的地址
    kind: 监视类型 (默认 write)
          - write: 监视写入
          - read: 监视读取
          - access: 监视读写

Example:
    watchpoint({"session_id": "abc", "address": "*0x7fffffff0000", "kind": "write"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "监视地址"},
                "kind": {
                    "type": "string",
                    "description": "监视类型: write/read/access",
                    "default": "write",
                },
            },
            "required": ["session_id", "address"],
        },
    ),

    # ── 执行控制 ──
    Tool(
        name="run",
        description="""运行程序 (args 可选)。

Args:
    session_id: 会话 ID
    args: 程序参数 (可选)

Example:
    run({"session_id": "abc", "args": "arg1 arg2"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "args": {
                    "type": "string",
                    "description": "程序参数",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="continue",
        description="""继续执行直到下一个断点或程序结束。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="step",
        description="""单步执行 (step into) - 进入函数内部。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="next",
        description="""单步执行 (step over) - 跳过函数调用。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),

    # ── 寄存器 / 栈 ──
    Tool(
        name="get_registers",
        description="""获取 CPU 寄存器状态。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_backtrace",
        description="""获取函数调用栈 (backtrace)。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="info_frame",
        description="""获取当前栈帧详细信息，包括参数、局部变量、帧地址等。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),

    # ── 反汇编 ──
    Tool(
        name="disassemble",
        description="""反汇编代码。

Args:
    session_id: 会话 ID
    location: 反汇编位置 (可选，默认为当前 PC)
    count: 指令数量 (默认 10)

Example:
    disassemble({"session_id": "abc", "location": "main", "count": 20})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "location": {
                    "type": "string",
                    "description": "反汇编位置",
                },
                "count": {
                    "type": "integer",
                    "description": "指令数量",
                    "default": 10,
                },
            },
            "required": ["session_id"],
        },
    ),

    # ── 内存 ──
    Tool(
        name="examine_memory",
        description="""检查内存内容 (默认 8 字节字组)。

Args:
    session_id: 会话 ID
    address: 内存地址或寄存器 (如 $rsp, 0x7fffffff0000)
    count: 显示单元数 (默认 16)

Examples:
    examine_memory({"session_id": "abc", "address": "$rsp", "count": 16})
    examine_memory({"session_id": "abc", "address": "0x7fffffffd000", "count": 8})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {
                    "type": "string",
                    "description": "内存地址或寄存器",
                },
                "count": {
                    "type": "integer",
                    "description": "显示单元数",
                    "default": 16,
                },
            },
            "required": ["session_id", "address"],
        },
    ),
    Tool(
        name="write_memory",
        description="""向内存地址写入值 (CTF 常用)。

Args:
    session_id: 会话 ID
    address: 目标地址 (如 0x7fffffff0000)
    value: 要写入的值 (如 0xdeadbeef)
    size: GDB 类型 (默认 int, 可选 char/long/short)

Example:
    write_memory({"session_id": "abc", "address": "0x601040", "value": "0xdeadbeef"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "目标地址"},
                "value": {"type": "string", "description": "要写入的值"},
                "size": {
                    "type": "string",
                    "description": "GDB 类型 (int/char/long/short)",
                    "default": "int",
                },
            },
            "required": ["session_id", "address", "value"],
        },
    ),
    Tool(
        name="patch_byte",
        description="""使用 GEF patch 命令修改内存字节。

Args:
    session_id: 会话 ID
    address: 目标地址
    bytes: 字节序列 (如 "\\\\x90\\\\x90\\\\x90" 或 "0x90 0x90")

Example:
    patch_byte({"session_id": "abc", "address": "0x401234", "bytes": "\\\\x90\\\\x90"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "目标地址"},
                "bytes": {"type": "string", "description": "字节序列"},
            },
            "required": ["session_id", "address", "bytes"],
        },
    ),
    Tool(
        name="hexdump",
        description="""使用 GEF hexdump 显示内存的十六进制 + ASCII 视图。

Args:
    session_id: 会话 ID
    address: 起始地址
    count: 字节数 (默认 64)
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "起始地址"},
                "count": {
                    "type": "integer",
                    "description": "字节数",
                    "default": 64,
                },
            },
            "required": ["session_id", "address"],
        },
    ),
    Tool(
        name="telescope",
        description="""GEF telescope 望远镜命令 —— 递归解引用内存。

从指定地址开始，逐层解引用显示地址链。

Args:
    session_id: 会话 ID
    address: 起始地址或寄存器 (如 $rsp)
    count: 显示层数 (默认 10)

Example:
    telescope({"session_id": "abc", "address": "$rsp", "count": 10})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {
                    "type": "string",
                    "description": "起始地址或寄存器",
                },
                "count": {
                    "type": "integer",
                    "description": "显示层数",
                    "default": 10,
                },
            },
            "required": ["session_id", "address"],
        },
    ),
    Tool(
        name="search_pattern",
        description="""在内存中搜索模式（字符串或十六进制）。

Args:
    session_id: 会话 ID
    pattern: 搜索模式

Examples:
    search_pattern({"session_id": "abc", "pattern": "/bin/sh"})
    search_pattern({"session_id": "abc", "pattern": "\\\\x48\\\\x31\\\\xf6"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "pattern": {"type": "string", "description": "搜索模式"},
            },
            "required": ["session_id", "pattern"],
        },
    ),
    Tool(
        name="search_strings",
        description="""在内存中搜索可打印字符串。

Args:
    session_id: 会话 ID
    pattern: 要搜索的字符串 (可选，留空搜索所有字符串)
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "pattern": {
                    "type": "string",
                    "description": "搜索字符串 (留空全搜)",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    ),

    # ── GEF 特色 ──
    Tool(
        name="vmmap",
        description="""显示进程虚拟内存映射。
包括堆、栈、代码段、共享库等所有映射区域。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="heap",
        description="""显示堆的详细信息 (chunk、arena 等)。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="checksec",
        description="""检查二进制安全缓解措施。
显示 NX, PIE, RELRO, Stack Canary, Fortify, ASLR 状态。
CTF 中常用作第一步信息收集。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="got_plt",
        description="""显示 GOT (Global Offset Table) / PLT 信息。
用于识别外部函数地址和进行 GOT 覆写攻击。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_context",
        description="""显示完整 GEF 调试上下文 (寄存器 + 栈 + 代码)。
在单步调试时用于全面了解程序状态。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_sections",
        description="""显示可执行文件的节区信息 (.text, .data, .bss 等)。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_entry_point",
        description="""显示程序的入口点地址。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="elf_info",
        description="""显示 ELF 文件头信息 (架构、入口点、段等)。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="reset_cache",
        description="""重置 GEF 缓存。当 GEF 显示信息不一致时使用。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),

    # ── CTF 专用 ──
    Tool(
        name="rop_search",
        description="""搜索 ROP gadgets。
CTF pwn 中用于构造 ROP 链的核心工具。

Args:
    session_id: 会话 ID
    gadget: 要搜索的 gadget (可选，如 "pop rdi; ret")
            留空显示常用 gadgets 摘要

Example:
    rop_search({"session_id": "abc", "gadget": "pop rdi"})
    rop_search({"session_id": "abc"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "gadget": {
                    "type": "string",
                    "description": "要搜索的 gadget (留空显示摘要)",
                    "default": "",
                },
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="rop_search_all",
        description="""搜索所有可用的 ROP gadgets (较慢)。
生成完整 gadgets 列表用于构造 ROP 链。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="attach_process",
        description="""附加到正在运行的进程进行调试。

Args:
    session_id: 会话 ID
    pid: 目标进程 ID

Example:
    attach_process({"session_id": "abc", "pid": 1234})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "pid": {
                    "type": "integer",
                    "description": "目标进程 ID",
                },
            },
            "required": ["session_id", "pid"],
        },
    ),
    Tool(
        name="detach_process",
        description="""从当前附加的进程分离。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="format_string_helper",
        description="""GEF format-string-helper —— 自动检测格式化字符串漏洞。
运行程序并自动分析 printf 调用中的格式化字符串参数。

Args:
    session_id: 会话 ID
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"}
            },
            "required": ["session_id"],
        },
    ),
    Tool(
        name="assemble",
        description="""在指定地址写入汇编指令 (GEF assemble)。
用于内存补丁和 Shellcode 注入。

Args:
    session_id: 会话 ID
    address: 目标地址 (如 0x401000)
    instruction: 汇编指令 (如 "mov eax, 0x1; ret")

Example:
    assemble({"session_id": "abc", "address": "0x401000", "instruction": "nop; ret"})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "目标地址"},
                "instruction": {
                    "type": "string",
                    "description": "汇编指令",
                },
            },
            "required": ["session_id", "address", "instruction"],
        },
    ),
    Tool(
        name="nop_sled",
        description="""在指定地址写入 NOP sled (NOP 指令序列)。
用于 Exploit 开发中的 NOP 填充。

Args:
    session_id: 会话 ID
    address: 起始地址
    count: NOP 数量 (默认 16)

Example:
    nop_sled({"session_id": "abc", "address": "0x7fffffffe000", "count": 256})
""",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "会话 ID"},
                "address": {"type": "string", "description": "起始地址"},
                "count": {
                    "type": "integer",
                    "description": "NOP 数量",
                    "default": 16,
                },
            },
            "required": ["session_id", "address"],
        },
    ),
]

# 工具名 → 回调函数映射
_TOOL_HANDLERS: dict[str, callable] = {
    "create_session": create_session_tool,
    "list_sessions": list_sessions_tool,
    "close_session": close_session_tool,
    "load_file": load_file_tool,
    "start_debugging": start_debugging_tool,
    "execute_command": execute_command_tool,
    "set_breakpoint": set_breakpoint_tool,
    "delete_breakpoint": delete_breakpoint_tool,
    "list_breakpoints": list_breakpoints_tool,
    "watchpoint": watchpoint_tool,
    "run": run_tool,
    "continue": continue_tool,
    "step": step_tool,
    "next": next_tool,
    "get_registers": get_registers_tool,
    "get_backtrace": get_backtrace_tool,
    "info_frame": info_frame_tool,
    "disassemble": disassemble_tool,
    "examine_memory": examine_memory_tool,
    "write_memory": write_memory_tool,
    "patch_byte": patch_byte_tool,
    "hexdump": hexdump_tool,
    "telescope": telescope_tool,
    "search_pattern": search_pattern_tool,
    "search_strings": search_strings_tool,
    "vmmap": vmmap_tool,
    "heap": heap_tool,
    "checksec": checksec_tool,
    "got_plt": got_plt_tool,
    "get_context": get_context_tool,
    "get_sections": get_sections_tool,
    "get_entry_point": get_entry_point_tool,
    "elf_info": elf_info_tool,
    "reset_cache": reset_cache_tool,
    "rop_search": rop_search_tool,
    "rop_search_all": rop_search_all_tool,
    "attach_process": attach_process_tool,
    "detach_process": detach_process_tool,
    "format_string_helper": format_string_helper_tool,
    "assemble": assemble_tool,
    "nop_sled": nop_sled_tool,
}


def dispatch_tool(name: str, arguments: dict) -> dict:
    """根据工具名分发到对应的回调函数"""
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    return handler(arguments or {})
