"""
Memory systems for Gweta Legal AI.

Provides:
- Short-term memory (conversation context in Redis)
- Long-term memory (user patterns in Firestore)
- Memory coordinator (unified interface)

Follows .cursorrules: async-first, token budget management, privacy-aware.
"""

from libs.memory.short_term import ShortTermMemory

__all__ = ["ShortTermMemory"]
