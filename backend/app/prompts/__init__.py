"""
Prompts package for the AI Data Analyst.
Contains expert system prompts and few-shot examples.
"""

from app.prompts.expert_prompts import (
    MASTER_ANALYST_SYSTEM_PROMPT,
    SCHEMA_FIRST_PROMPT,
    COLUMN_SELECTION_PROMPT,
    ERROR_CORRECTION_PROMPT,
    FEW_SHOT_EXAMPLES,
    format_schema_for_prompt,
    get_error_fix_prompt
)

__all__ = [
    'MASTER_ANALYST_SYSTEM_PROMPT',
    'SCHEMA_FIRST_PROMPT',
    'COLUMN_SELECTION_PROMPT',
    'ERROR_CORRECTION_PROMPT',
    'FEW_SHOT_EXAMPLES',
    'format_schema_for_prompt',
    'get_error_fix_prompt'
]
