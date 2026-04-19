import pandas as pd

from app.agents.utility.FewShotExampleStore import Visualization_FewShotExampleStore
from app.agents.utility.AnalysisToolFactory import AnalysisToolFactory


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