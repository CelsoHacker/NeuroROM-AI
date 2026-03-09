"""ROM Translation Framework - Core Module"""

try:
    from .box_profile_manager import BoxProfileManager
except Exception:
    BoxProfileManager = None

try:
    from .console_memory_model import ConsoleMemoryModel
except Exception:
    ConsoleMemoryModel = None

try:
    from .encoding_adapter import EncodingAdapter
except Exception:
    EncodingAdapter = None

try:
    from .auto_text_auditor import AutoTextAuditor
except Exception:
    AutoTextAuditor = None

try:
    from .glyph_metrics import GlyphMetrics
except Exception:
    GlyphMetrics = None

try:
    from .relocation_manager import RelocationManager
except Exception:
    RelocationManager = None

try:
    from .runtime_qa_simulator import RuntimeQASimulator
except Exception:
    RuntimeQASimulator = None

try:
    from .text_layout_engine import TextLayoutEngine
except Exception:
    TextLayoutEngine = None

__all__ = [
    "AutoTextAuditor",
    "GlyphMetrics",
    "TextLayoutEngine",
    "BoxProfileManager",
    "EncodingAdapter",
    "ConsoleMemoryModel",
    "RuntimeQASimulator",
    "RelocationManager",
]
