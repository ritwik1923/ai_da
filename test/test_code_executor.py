import os
import sys

import pandas as pd

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.utils.code_executor import safe_execute_pandas_code


def test_safe_execute_pandas_code_supports_plotly_express_result():
    df = pd.DataFrame(
        {
            "Sleep_Hours": [6.5, 7.0, 8.0],
            "Stress_Level": [7, 5, 4],
        }
    )

    code = "result = px.scatter(df, x='Sleep_Hours', y='Stress_Level', title='Sleep vs Stress')"
    execution_result = safe_execute_pandas_code(code, df)

    assert execution_result["type"] == "plotly_figure"
    assert execution_result["trace_count"] == 1
    assert execution_result["title"] == "Sleep vs Stress"
