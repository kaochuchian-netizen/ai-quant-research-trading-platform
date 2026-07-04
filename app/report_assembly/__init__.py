"""Context-based report assembly foundation."""
from .builder import build_context_based_report_assembly_artifact
from .schemas import SCHEMA_VERSION

__all__ = ["SCHEMA_VERSION", "build_context_based_report_assembly_artifact"]
