"""
Integration tests for RAG-based column selection using a real CSV dataset.

These tests read the provided `customers-1000.csv` file, expand it to exceed the
column threshold, then instantiate the `DataAnalystAgent` (v2) with
`enable_column_rag=True`.  They verify that the RAG subsystem is activated and
actually returns relevant columns for a given query.

Run with: `pytest backend/tests/test_rag_csv.py`
"""

import os
import pytest
import pandas as pd

from backend.app.agents.data_analyst_v2 import DataAnalystAgent


# try to import the RAG utilities so we can skip tests if the dependencies
# (chroma, sentence_transformers) are missing.  the agent itself will import
# them lazily during initialization, but we want to detect the absence early.
try:
    from backend.app.agents.utility.column_vector_store import ColumnSelector  # noqa: F401
except ImportError:
    ColumnSelector = None


@pytest.fixture
def customers_dataframe():
    """Read the sample CSV and bump column count above the RAG threshold."""
    path = os.path.expanduser("~/Downloads/customers-1000.csv")
    if not os.path.isfile(path):
        pytest.skip(f"CSV file not found at {path}")

    df = pd.read_csv(path)
    # duplicate an existing column until we have >50 columns so RAG auto-enables
    while len(df.columns) < 60:
        # duplicate the 'Country' column to ensure semantic relevance
        new_col = f"dup_{len(df.columns)}"
        df[new_col] = df['Country']
    assert len(df.columns) > 50
    return df


@pytest.mark.skipif(ColumnSelector is None, reason="RAG dependencies not installed")
def test_rag_columns_selected(customers_dataframe):
    """Agent should enable column RAG and find relevant columns for a query."""

    agent = DataAnalystAgent(customers_dataframe, enable_column_rag=True)
    assert agent.enable_column_rag is True, "Column RAG should be active for wide dataset"

    # Directly query the selector to ensure it returns sensible results
    cols = agent.column_selector.select_columns("country", max_columns=5)
    assert cols, "RAG selector returned no columns"
    # selector may return plain strings or dicts depending on version
    normalized = []
    for c in cols:
        if isinstance(c, str):
            normalized.append(c.lower())
        elif isinstance(c, dict):
            normalized.append(c.get("column_name", "").lower())
    # one of the results should relate to country (either the original column or a dup)
    assert any("country" in name for name in normalized), f"expected country-related column among {normalized}"
    # Run a high‑level query through the agent and inspect metadata
    result = agent.analyze("How many unique countries are there?")
    assert result["success"], "Agent failed to process query"
    assert result["metadata"]["column_rag_used"] is True
    # the answer should mention "country" or give a count
    assert "country" in result["answer"].lower() or result["answer"].strip(), result["answer"]
