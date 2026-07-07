# GEF MCP Server v2.0

**玄幕安全团队 - guaidao2 开发** 🛡️

**GDB Enhanced Features** 的 Model Context Protocol (MCP) 服务器实现，支持通过 SSE 或 stdio 进行远程调试。专为安全测试和 CTF 竞赛优化。

## 特性

- **GEF/GDB 集成**: 自动加载 GEF 插件，提供增强调试能力
- **多会话**: 最多 4 个并发调试会话
- **SSE + stdio 双模式**: 远程 HTTP SSE 或本地 Claude Desktop stdio
- **PTY 终端**: 真实终端模拟，支持交互式调试
- **40+ 专用工具**: 覆盖调试、内存操作、二进制分析、CTF exploit 开发全流程
- **CTF 定向增强**: checksec、ROP 搜索、format-string 检测、patch、assemble 等
- **安全防护**: 路径注入消杀、换行防护、输出大小限制
- **后台僵尸回收**: 自动清理崩溃的会话

## 安装

```bash
cd /root/Desktop/gef-mcp
pip install -r requirements.txt
```

### 安装 GEF（如未安装）

```bash
bash -c "$(curl -fsSL https://gef.blah.cat/sh)"
```

## 使用

```bash
# SSE 模式 (默认 :8000)
python server.py

# 指定地址和端口
python server.py --host 127.0.0.1 --port 8080

# stdio 模式 (Claude Desktop)
python server.py --transport stdio
```

### MCP 端点

- SSE 端点: `http://localhost:8000/sse`
- 消息端点: `http://localhost:8000/messages/`

## 工具列表

### 会话管理

| 工具 | 描述 |
|------|------|
| `create_session` | 创建新调试会话 |
| `list_sessions` | 列出所有活跃会话 |
| `close_session` | 关闭会话 |

### 文件与启动

| 工具 | 描述 |
|------|------|
| `load_file` | 加载目标二进制 |
| `start_debugging` | 加载文件 + 显示 GEF 上下文 |

### 断点

| 工具 | 描述 |
|------|------|
| `set_breakpoint` | 设置断点 (函数/地址/文件:行) |
| `delete_breakpoint` | 按编号删除断点 |
| `list_breakpoints` | 列出所有断点/监视点 |
| `watchpoint` | 设置数据断点 (读/写/访问) |

### 执行控制

| 工具 | 描述 |
|------|------|
| `run` | 运行程序 (带参数) |
| `continue` | 继续执行 |
| `step` | 单步进入 |
| `next` | 单步跳过 |

### 寄存器 / 栈

| 工具 | 描述 |
|------|------|
| `get_registers` | 获取 CPU 寄存器 |
| `get_backtrace` | 函数调用回溯 |
| `info_frame` | 当前栈帧详细信息 |

### 反汇编

| 工具 | 描述 |
|------|------|
| `disassemble` | 反汇编代码 |

### 内存操作

| 工具 | 描述 |
|------|------|
| `examine_memory` | 检查内存 (x/8xg) |
| `write_memory` | 向内存写入值 |
| `patch_byte` | GEF patch 修改字节 |
| `hexdump` | 十六进制 + ASCII 视图 |
| `telescope` | 递归解引用 (望远镜) |
| `search_pattern` | 搜索内存模式 |
| `search_strings` | 搜索可打印字符串 |

### GEF 增强

| 工具 | 描述 |
|------|------|
| `vmmap` | 虚拟内存映射 |
| `heap` | 堆信息 |
| `checksec` | 🔐 安全缓解措施检查 |
| `got_plt` | GOT/PLT 信息 |
| `get_context` | 完整调试上下文 |
| `get_sections` | 节区信息 |
| `get_entry_point` | 入口点地址 |
| `elf_info` | ELF 文件头信息 |
| `reset_cache` | 重置 GEF 缓存 |

### CTF 专用 🔥

| 工具 | 描述 |
|------|------|
| `rop_search` | 搜索 ROP gadgets |
| `rop_search_all` | 列出所有 gadgets |
| `attach_process` | 附加到进程 |
| `detach_process` | 从进程分离 |
| `format_string_helper` | 检测格式化字符串漏洞 |
| `assemble` | 写入汇编指令 |
| `nop_sled` | 写入 NOP chain |
| `execute_command` | 任意 GEF/GDB 命令 |

## 与 Claude Desktop 集成

```json
{
  "mcpServers": {
    "gef": {
      "command": "python",
      "args": ["/root/Desktop/gef-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```

## 安全说明

- `filepath` 参数经过注入消杀，拒绝含有 `!` `;` `|` 等 shell 元字符的路径
- `pattern` 参数拒绝换行符，防止命令注入
- `execute_command` 按设计执行任意命令——请确保调用来源可信
- 所有会话输出有 50KB 大小限制，防止内存膨胀

## 调试流程示例 (CTF)

```python
# 1. 创建会话
session = await call_tool("create_session", {})
sid = session["session_id"]

# 2. 加载目标
await call_tool("load_file", {"session_id": sid, "filepath": "./vuln"})

# 3. 安全检查
sec = await call_tool("checksec", {"session_id": sid})
# → NX: enabled | PIE: disabled | Canary: enabled ...

# 4. 查看内存布局
map = await call_tool("vmmap", {"session_id": sid})

# 5. 断点 + 运行
await call_tool("set_breakpoint", {"session_id": sid, "location": "main"})
await call_tool("run", {"session_id": sid})

# 6. 搜索 ROP gadgets
gadgets = await call_tool("rop_search", {"session_id": sid, "gadget": "pop rdi"})

# 7. 检查 GOT
got = await call_tool("got_plt", {"session_id": sid})

# 8. 修改内存
await call_tool("write_memory", {
    "session_id": sid,
    "address": "0x601040",
    "value": "0xdeadbeef"
})
```

## 许可证

MIT
