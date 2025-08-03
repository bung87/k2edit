"""Memory Store Configuration for K2Edit
Uses ChromaDB as the primary memory store.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class MemoryStoreConfig:
    """Configuration for ChromaDB memory store"""
    chroma_host: Optional[str] = None
    chroma_port: Optional[int] = None
    chroma_settings: Optional[dict] = None
    
    @classmethod
    def from_env(cls) -> "MemoryStoreConfig":
        """Create configuration from environment variables"""
        return cls(
            chroma_host=os.getenv("K2EDIT_CHROMA_HOST"),
            chroma_port=int(os.getenv("K2EDIT_CHROMA_PORT", "8000")) if os.getenv("K2EDIT_CHROMA_PORT") else None,
            chroma_settings={
                "anonymized_telemetry": False,
                "allow_reset": True
            }
        )


def create_memory_store(context_manager, logger=None, config: Optional[MemoryStoreConfig] = None):
    """Factory function to create ChromaDB memory store"""
    from .chroma_memory_store import ChromaMemoryStore
    return ChromaMemoryStore(context_manager, logger)