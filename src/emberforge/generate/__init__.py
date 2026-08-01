"""Candidate generators: templates, mutation, and optional AI (mock by default)."""

from .ai import AISchemaError, MockProvider, generate_ai, parse_ai_factor, prompt_hash
from .mutate import mutate_family, mutate_horizon
from .templates import TEMPLATES, generate_templates

__all__ = [
    "generate_templates", "TEMPLATES",
    "mutate_horizon", "mutate_family",
    "generate_ai", "parse_ai_factor", "MockProvider", "AISchemaError", "prompt_hash",
]
