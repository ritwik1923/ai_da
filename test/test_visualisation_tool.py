import pandas as pd

from app.agents.utility.FewShotExampleStore import Visualization_FewShotExampleStore
from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory
from app.agents.DataAnalystAgent import DataAnalystAgent


class DummyCodeService:
    def __init__(self):
        self.last_task = None

    def generate_visualization_code(self, task, top_n=10):
        self.last_task = (task, top_n)
        return {
            "success": True,
            "code": "result = 'ok'",
            "examples": "Similar Task: Price Distribution by Category",
            "top_n": top_n,
        }

    def generate_and_execute(self, task):
        return {"success": True, "result": task, "code": "result = 1"}


class DummyPassport:
    def to_prompt_context(self):
        return "schema"


def test_visualization_store_has_price_distribution_golden_example():
    example = next(
        item for item in Visualization_FewShotExampleStore.visualization_golden_examples
        if item["task"] == "Price Distribution by Category"
    )

    assert example["chart_family"] == "ranked_horizontal_bar"
    assert "Aggregate price by category" in example["template"]
    assert "top 10" in example["rationale"].lower()
    assert "Top 10 Categories by Total Price" in example["code"]


def test_visualisation_tool_returns_rag_examples():
    factory = AnalysisToolFactory(DummyPassport(), DummyCodeService(), pd.DataFrame({"Price": [1, 2]}))
    tools = {tool.name: tool for tool in factory.create_tools()}

    payload = tools["visualisation_tool"].func("Price Distribution by Category")

    assert "visualisation_tool" in payload
    assert "Similar Task: Price Distribution by Category" in payload


def test_visualization_plan_covers_major_families():
    agent = DataAnalystAgent.__new__(DataAnalystAgent)
    agent.df = pd.DataFrame(
        {
            "Category": ["A", "B", "A", "C", "B", "A", "C", "B", "A", "C"],
            "Region": ["North", "South", "East", "West", "South", "North", "West", "East", "North", "West"],
            "Channel": ["Online", "Store", "Store", "Online", "Online", "Store", "Online", "Store", "Online", "Store"],
            "OrderDate": [
                "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05",
                "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10",
            ],
            "Price": [10, 20, 18, 22, 20, 16, 19, 23, 17, 21],
            "Stock": [4, 5, 4, 6, 5, 4, 6, 5, 4, 6],
            "Margin": [2.1, 2.8, 2.4, 3.0, 2.7, 2.2, 3.1, 2.9, 2.3, 3.0],
        }
    )

    plan = agent.build_visualization_plan()
    families = {item["family"] for item in plan}
    fallback = agent.build_fallback_visual_recommendations()

    assert {"ranking", "relationship", "trend", "distribution", "breakdown"}.issubset(families)
    assert fallback is not None
    assert 10 <= len(plan) <= 15
    assert 10 <= len(fallback) <= 15
    queries = [item["suggested_query"] for item in fallback]
    assert len(queries) == len(set(queries))