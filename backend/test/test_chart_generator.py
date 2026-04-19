import pandas as pd

from app.utils.chart_generator import generate_chart_from_query


def test_relationship_query_uses_aggregated_category_scatter():
    df = pd.DataFrame(
        {
            "Category": ["A", "A", "B", "B", "C", "C"],
            "Price": [100, 120, 200, 220, 300, 330],
            "Stock": [10, 12, 20, 18, 30, 28],
            "Name": ["p1", "p2", "p3", "p4", "p5", "p6"],
        }
    )

    chart = generate_chart_from_query(df, "Show the relationship between price and stock by category")

    assert chart is not None
    assert chart["type"] == "scatter"

    figure_data = chart["data"]
    trace_names = {trace.get("name") for trace in figure_data.get("data", [])}
    assert trace_names == {"A", "B", "C"}

    for trace in figure_data.get("data", []):
        assert len(trace.get("x", [])) == 1
        assert len(trace.get("y", [])) == 1
        assert trace.get("text")

    title_text = figure_data.get("layout", {}).get("title", {}).get("text", "")
    assert "average stock" in title_text.lower()
    assert "average price" in title_text.lower()
    assert "category" in title_text.lower()