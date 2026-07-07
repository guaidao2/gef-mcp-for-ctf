"""
GEF MCP 会话管理 —— PTY 封装、GDB/GEF 命令执行

玄幕安全团队 - guaidao2 开发
"""

import os
import pty
import select
import signal
import time
import threading
from typing import Optional

from utils import clean_output, sanitize_filepath, sanitize_pattern, log


class GefSession:
    """GEF/GDB 调试会话 (PTY 封装)"""

    def __init__(self, session_id: str, timeout: int = 10):
        self.session_id = session_id
        self.timeout = timeout
        self.master_fd: Optional[int] = None
        self.child_pid: Optional[int] = None
        self.ps1_marker = f"GEF_MCP_END_{session_id}"
        self._lock = threading.Lock()
        self._closed = False
        self.target_file: Optional[str] = None
        self._init_pty()

    # ── PTY 初始化 ──────────────────────────────────────────────

    def _init_pty(self):
        """fork PTY，子进程 exec GEF/GDB"""
        env = os.environ.copy()
        env['PS1'] = f'\\[{self.ps1_marker}\\]\\$ '
        env['TERM'] = 'xterm-256color'

        self.child_pid, self.master_fd = pty.fork()

        if self.child_pid == 0:
            # ── 子进程 ──
            try:
                gef_path = self._find_gef()
                if gef_path:
                    log.info("Starting GEF from %s", gef_path)
                    os.execv(gef_path, [gef_path, '-q'])
                else:
                    gdb_path = self._find_gdb()
                    log.info("Starting GDB from %s (gef will be sourced)", gdb_path)
                    os.execv(gdb_path, [gdb_path, '-q', '--nh'])
            except Exception as e:
                os._exit(1)
        else:
            # ── 父进程 ──
            time.sleep(0.5)
            self._setup_gef()

    def _find_gdb(self) -> str:
        """查找 GDB 路径"""
        for path in ['/usr/bin/gdb', '/usr/local/bin/gdb']:
            if os.path.exists(path):
                return path
        return 'gdb'  # fallback, rely on PATH

    def _find_gef(self) -> Optional[str]:
        """查找 GEF 命令路径 (Kali 新版本)"""
        for path in ['/usr/bin/gef', '/usr/local/bin/gef']:
            if os.path.exists(path):
                return path
        return None

    # ── GEF 配置 ────────────────────────────────────────────────

    def _setup_gef(self):
        """加载 GEF 插件并初始化配置"""
        with self._lock:
            if self._closed:
                return

            gef_paths = [
                '/tmp/gef.py',
                os.path.expanduser('~/.gdbinit-gef.py'),
                os.path.expanduser('~/.gef.py'),
                '/usr/share/gef/gef.py',
                '/opt/gef/gef.py',
            ]

            gef_loaded = False
            for gef_path in gef_paths:
                if os.path.exists(gef_path):
                    log.info("Loading GEF from %s", gef_path)
                    self._write(f'source {gef_path}')
                    gef_loaded = True
                    break

            if not gef_loaded:
                log.warning("GEF not found locally, trying ~/.gdbinit-gef.py")
                self._write('source ~/.gdbinit-gef.py 2>/dev/null')

            # GEF 基本配置
            self._write('gef config context.clear_screen False')
            self._write('gef config context.layout "regs stack code source"')
            self._write('set pagination off')
            self._write('set confirm off')
            time.sleep(0.3)
            # 清掉初始化阶段的输出
            self._drain()

    # ── 底层 PTY 读写 ───────────────────────────────────────────

    def _write(self, command: str) -> bool:
        """向 PTY 写入命令

        Returns:
            True 表示写入成功，False 表示会话已关闭或写入失败
        """
        if self._closed or self.master_fd is None:
            return False
        try:
            os.write(self.master_fd, f'{command}\n'.encode())
            return True
        except OSError as e:
            log.error("Write to PTY failed: %s", e)
            return False

    def _drain(self, timeout: float = 0.3) -> str:
        """排空当前可用输出（不等待 prompt）"""
        output = []
        end_time = time.time() + timeout

        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            try:
                ready, _, _ = select.select([self.master_fd], [], [], min(0.05, remaining))
                if ready:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        output.append(data.decode('utf-8', errors='replace'))
                    else:
                        break
                # else: 继续等待，不 break —— 有循环超时兜底
            except (OSError, TypeError):
                break

        return ''.join(output)

    def _read_until_prompt(self, timeout: float = None) -> str:
        """读取 PTY 输出直到 GEF 提示符出现或超时"""
        if timeout is None:
            timeout = self.timeout

        output = []
        end_time = time.time() + timeout
        gef_prompt_found = False

        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            try:
                ready, _, _ = select.select([self.master_fd], [], [], min(0.05, remaining))
                if ready:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        text = data.decode('utf-8', errors='replace')
                        output.append(text)
                        # 检测 GEF / GDB 提示符
                        if ('gef➤' in text or '(gdb)' in text
                                or self.ps1_marker in text):
                            gef_prompt_found = True
                            break
                    else:
                        break  # EOF 子进程退出
            except OSError:
                break

        result = ''.join(output)
        if not gef_prompt_found:
            log.warning("Session %s: timeout waiting for prompt (%.1fs)",
                        self.session_id, timeout)
            result += "\n[Warning: Timeout waiting for GEF prompt]\n"

        return result

    # ── 命令执行 ────────────────────────────────────────────────

    def execute_gef_command(self, command: str,
                            extended_timeout: bool = False) -> str:
        """执行 GEF/GDB 命令

        Args:
            command: GEF/GDB 命令
            extended_timeout: 对 run/continue 等长时间命令使用 3 倍超时

        Returns:
            清理后的命令输出
        """
        with self._lock:
            if self._closed:
                return "Error: Session has been closed"
            if not command.strip():
                return ""

            log.debug("Session %s: exec: %s", self.session_id,
                      command[:120])

            sent = self._write(command)
            if not sent:
                return "Error: Failed to write command to PTY"

            time.sleep(0.1)

            if extended_timeout:
                output = self._read_until_prompt(timeout=self.timeout * 3)
            else:
                output = self._read_until_prompt()

            return clean_output(output)

    # ── 高级调试方法 ────────────────────────────────────────────

    def load_file(self, filepath: str) -> str:
        """加载目标文件"""
        filepath = sanitize_filepath(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"

        self.target_file = filepath
        log.info("Session %s: loading file %s", self.session_id, filepath)
        return self.execute_gef_command(f'file {filepath}')

    def start_debugging(self, filepath: str) -> str:
        """加载文件并显示 GEF 上下文"""
        filepath = sanitize_filepath(filepath)
        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"

        self.target_file = filepath
        log.info("Session %s: start debugging %s", self.session_id, filepath)

        gef_path = self._find_gef()
        result = self.execute_gef_command(f'file {filepath}')
        if gef_path:
            ctx = self.execute_gef_command('context')
            return f"Loaded with GEF: {filepath}\n{result}\n{ctx}"
        return result

    # ── 基础调试操作 ────────────────────────────────────────────

    def set_breakpoint(self, location: str) -> str:
        return self.execute_gef_command(f'break {location}')

    def run(self, args: str = "") -> str:
        cmd = f'run {args}' if args else 'run'
        return self.execute_gef_command(cmd, extended_timeout=True)

    def continue_execution(self) -> str:
        return self.execute_gef_command('continue', extended_timeout=True)

    def step(self) -> str:
        return self.execute_gef_command('step')

    def next(self) -> str:
        return self.execute_gef_command('next')

    def examine_memory(self, address: str, count: int = 16) -> str:
        return self.execute_gef_command(f'x/{count}xg {address}')

    def disassemble(self, location: str = None, count: int = 10) -> str:
        if location:
            return self.execute_gef_command(
                f'disassemble {location},+{count * 4}')
        return self.execute_gef_command(f'x/{count}i $pc')

    def get_registers(self) -> str:
        return self.execute_gef_command('info registers')

    def get_backtrace(self) -> str:
        return self.execute_gef_command('backtrace')

    def search_pattern(self, pattern: str) -> str:
        pattern = sanitize_pattern(pattern)
        return self.execute_gef_command(f'search-pattern {pattern}')

    def vmmap(self) -> str:
        return self.execute_gef_command('vmmap')

    def heap(self) -> str:
        return self.execute_gef_command('heap')

    def telescope(self, address: str, count: int = 10) -> str:
        return self.execute_gef_command(f'telescope {address} {count}')

    # ── CTF 专用工具方法 ────────────────────────────────────────

    def checksec(self) -> str:
        """检查二进制安全缓解措施 (NX / PIE / RELRO / Canary / Fortify)"""
        return self.execute_gef_command('checksec')

    def set_watchpoint(self, address: str, kind: str = "write") -> str:
        """设置数据断点

        Args:
            address: 监视地址
            kind: write | read | access (rwatch | awatch)
        """
        cmd_map = {"write": "watch", "read": "rwatch", "access": "awatch"}
        gdb_cmd = cmd_map.get(kind, "watch")
        return self.execute_gef_command(f'{gdb_cmd} {address}')

    def delete_breakpoint(self, number: int) -> str:
        """按编号删除断点"""
        return self.execute_gef_command(f'delete {number}')

    def list_breakpoints(self) -> str:
        """列出所有断点/监视点"""
        return self.execute_gef_command('info breakpoints')

    def write_memory(self, address: str, value: str,
                     size: str = "int") -> str:
        """向内存地址写入值

        Args:
            address: 目标地址 (如 0x7fffffff0000)
            value:  要写入的值 (如 0xdeadbeef)
            size:   gdb 类型 (int, char, long, etc.)
        """
        return self.execute_gef_command(
            f'set ({size}*){address} = {value}')

    def patch_byte(self, address: str, byte_str: str) -> str:
        """使用 GEF 的 patch 命令修改内存字节

        Args:
            address: 目标地址
            byte_str: 字节序列 (如 "\\x90\\x90" 或 "0x90 0x90")
        """
        return self.execute_gef_command(f'patch {address} {byte_str}')

    def rop_search(self, gadget: str = "") -> str:
        """搜索 ROP gadgets

        Args:
            gadget: 要搜索的 gadget 助记符 (如 "pop rdi; ret")
                    留空则列出所有常见 gadgets
        """
        if gadget:
            return self.execute_gef_command(f'rop --gadget {gadget}')
        return self.execute_gef_command('rop')

    def rop_search_all(self) -> str:
        """列出所有 ROP gadgets (较慢)"""
        return self.execute_gef_command('ropgadget')

    def got_plt(self) -> str:
        """显示 GOT/PLT 信息"""
        return self.execute_gef_command('got')

    def attach_process(self, pid: int) -> str:
        """附加到运行中的进程"""
        return self.execute_gef_command(f'attach {pid}',
                                        extended_timeout=True)

    def detach_process(self) -> str:
        """从当前进程分离"""
        return self.execute_gef_command('detach')

    def info_frame(self) -> str:
        """获取当前栈帧信息"""
        return self.execute_gef_command('info frame')

    def get_context(self) -> str:
        """显示完整 GEF 上下文 (regs + stack + code)"""
        return self.execute_gef_command('context')

    def hexdump(self, address: str, count: int = 64) -> str:
        """使用 GEF hexdump 显示内存

        Args:
            address: 起始地址
            count:   字节数
        """
        return self.execute_gef_command(f'hexdump qword {address} {count}')

    def format_string_helper(self) -> str:
        """GEF format-string-helper：自动检测格式化字符串漏洞"""
        return self.execute_gef_command('format-string-helper',
                                        extended_timeout=True)

    def search_strings(self, pattern: str = "") -> str:
        """在内存中搜索字符串

        Args:
            pattern: 要搜索的字符串 (留空搜索所有可打印字符串)
        """
        if pattern:
            return self.execute_gef_command(f'search-pattern "{pattern}"')
        return self.execute_gef_command('strings')

    def assemble(self, address: str, instruction: str) -> str:
        """在指定地址写入汇编指令 (GEF assemble)"""
        return self.execute_gef_command(
            f'assemble {address} {instruction}')

    def nop_sled(self, address: str, count: int = 16) -> str:
        """在指定地址写入 NOP sled"""
        return self.execute_gef_command(f'nop {address} {count}')

    def reset_cache(self) -> str:
        """重置 GEF 缓存"""
        return self.execute_gef_command('reset-cache')

    def get_sections(self) -> str:
        """显示段信息"""
        return self.execute_gef_command('info files')

    def get_entry_point(self) -> str:
        """显示入口点"""
        return self.execute_gef_command('info entry')

    def get_elf_info(self) -> str:
        """显示 ELF 文件信息"""
        return self.execute_gef_command('elf-info')

    # ── 生命周期 ────────────────────────────────────────────────

    def close(self):
        """关闭会话：终止子进程并关闭 PTY"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            log.info("Closing session %s", self.session_id)

            # 先关闭 fd 让子进程读不到输入
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except Exception:
                    pass
                self.master_fd = None

            # 终止子进程：先 SIGTERM 再 SIGKILL
            if self.child_pid is not None:
                try:
                    os.kill(self.child_pid, signal.SIGTERM)
                    # 给子进程 0.5s 优雅退出
                    for _ in range(5):
                        time.sleep(0.1)
                        try:
                            os.kill(self.child_pid, 0)
                        except OSError:
                            self.child_pid = None
                            break
                    else:
                        # 仍未退出，强制 SIGKILL
                        if self.child_pid:
                            os.kill(self.child_pid, signal.SIGKILL)
                except Exception:
                    pass
                self.child_pid = None

    def is_alive(self) -> bool:
        """检查子进程是否存活"""
        if self._closed or self.child_pid is None:
            return False
        try:
            os.kill(self.child_pid, 0)
            return True
        except OSError:
            self._closed = True
            return False
