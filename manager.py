"""
GEF MCP 会话管理器 —— 会话生命周期管理 + 后台僵尸回收

玄幕安全团队 - guaidao2 开发
"""

import threading
import time
import uuid
from typing import Dict, Any, Optional

from session import GefSession
from utils import log

REAPER_INTERVAL = 60  # 僵尸回收检查间隔（秒）


class SessionManager:
    """GEF 会话管理器

    职责:
    - 创建 / 获取 / 关闭会话
    - 后台线程自动回收僵尸会话
    - 限制最大并发会话数
    """

    MAX_SESSIONS = 4

    def __init__(self):
        self._sessions: Dict[str, GefSession] = {}
        self._lock = threading.Lock()
        self._reaper_stop = threading.Event()
        self._reaper_thread = threading.Thread(
            target=self._reaper_loop,
            name="session-reaper",
            daemon=True,
        )
        self._reaper_thread.start()
        log.info("SessionManager initialized (max %d sessions, reaper every %ds)",
                 self.MAX_SESSIONS, REAPER_INTERVAL)

    # ── 公共 API ────────────────────────────────────────────────

    def create_session(self, timeout: int = 10) -> Dict[str, Any]:
        """创建新 GEF 调试会话"""
        with self._lock:
            if len(self._sessions) >= self.MAX_SESSIONS:
                return {
                    "success": False,
                    "error": f"Maximum session limit ({self.MAX_SESSIONS}) reached. "
                             f"Close an existing session first.",
                }

            session_id = str(uuid.uuid4())
            log.info("Creating session %s (timeout=%ds)", session_id, timeout)

            try:
                session = GefSession(session_id, timeout)
                time.sleep(0.5)

                if session.is_alive():
                    self._sessions[session_id] = session
                    return {
                        "success": True,
                        "session_id": session_id,
                        "message": "GEF session created successfully",
                    }
                else:
                    log.error("Session %s failed to initialize", session_id)
                    return {
                        "success": False,
                        "error": "Failed to initialize GEF session. "
                                 "Is GDB/GEF installed?",
                    }
            except Exception as e:
                log.exception("Session creation error")
                return {
                    "success": False,
                    "error": f"Error creating session: {str(e)}",
                }

    def get_session(self, session_id: str) -> Optional[GefSession]:
        """获取会话对象"""
        with self._lock:
            return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> Dict[str, Any]:
        """关闭指定会话"""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                }

            session.close()
            del self._sessions[session_id]
            log.info("Session %s closed", session_id)

            return {
                "success": True,
                "message": f"Session {session_id} closed",
                "active_sessions": len(self._sessions),
            }

    def list_sessions(self) -> Dict[str, Any]:
        """列出所有会话"""
        with self._lock:
            sessions_info = []
            for sid, session in list(self._sessions.items()):
                alive = session.is_alive()
                sessions_info.append({
                    "session_id": sid,
                    "alive": alive,
                    "target": session.target_file,
                })
                if not alive:
                    # 标记为死掉的会话，稍后 reaper 会清理
                    log.warning("Session %s is dead", sid)

            return {
                "success": True,
                "total": len(sessions_info),
                "max_sessions": self.MAX_SESSIONS,
                "sessions": sessions_info,
            }

    def close_all(self):
        """关闭所有会话"""
        log.info("Closing all sessions")
        with self._lock:
            for session in list(self._sessions.values()):
                session.close()
            self._sessions.clear()

    def active_count(self) -> int:
        """当前活跃会话数"""
        with self._lock:
            return len(self._sessions)

    # ── 后台僵尸回收 ────────────────────────────────────────────

    def _reaper_loop(self):
        """后台线程：定期回收死掉的会话"""
        while not self._reaper_stop.is_set():
            time.sleep(REAPER_INTERVAL)
            self._reap_zombies()

    def _reap_zombies(self):
        """扫描并关闭所有不活跃的会话"""
        reaped = []
        with self._lock:
            for sid, session in list(self._sessions.items()):
                if not session.is_alive():
                    reaped.append(sid)
                    try:
                        session.close()
                    except Exception:
                        pass
                    del self._sessions[sid]

        if reaped:
            log.info("Reaped %d zombie session(s): %s", len(reaped),
                     ", ".join(reaped[:5]) + ("..." if len(reaped) > 5 else ""))

    def stop_reaper(self):
        """停止后台回收线程"""
        self._reaper_stop.set()
        self._reaper_thread.join(timeout=5)


# 全局单例
session_manager = SessionManager()
