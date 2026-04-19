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


def test_price_distribution_by_category_defaults_to_top_10_ranked_bar():
    df = pd.DataFrame(
        {
            "Category": [f"C{i}" for i in range(12)],
            "Price": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
        }
    )

    chart = generate_chart_from_query(df, "Price Distribution by Category")

    assert chart is not None
    assert chart["type"] == "bar"
    figure_data = chart["data"]
    trace = figure_data["data"][0]
    assert len(trace.get("x", [])) == 10
    assert figure_data.get("layout", {}).get("title", {}).get("text", "").lower().startswith("top 10")