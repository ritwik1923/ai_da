import pandas as pd

# from app.utils.chart_generator import generate_chart, generate_chart_from_query
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.agents.DataAnalystAgent import DataAnalystAgent, AgentGlobals
import plotly.graph_objects as go
import json
import logging
from typing import List

import asyncio
from app.utils.chart_generator import generate_chart, generate_chart_from_query
import glob
from starlette.concurrency import run_in_threadpool



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_chart_yaml_as_json(yaml_path: str) -> dict:
    """Load chart_gen.yml into a JSON-compatible dictionary."""
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    data_file = None
    tasks: List[dict] = []

    with open(yaml_path, "r", encoding="utf-8") as yml_file:
        for raw_line in yml_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("- file:"):
                value = line.split(":", 1)[1].strip().strip("\"'")
                data_file = value or None
                continue

            if line.startswith("query:"):
                value = line.split(":", 1)[1].strip().strip("\"'")
                if value:
                    tasks.append({"query": value})

    return {
        "test_cases": [
            {
                "file": data_file,
                "tasks": tasks,
            }
        ]
    }


def load_test_cases_json(file_path):
    """Loads cases from YAML file and returns JSON-like test_cases list."""
    try:
        data = _load_chart_yaml_as_json(file_path)
        return data.get("test_cases", [])
    except FileNotFoundError:
        logger.error(f"❌ YAML file not found at {file_path}")
        return []
    except Exception as exc:
        logger.error(f"❌ Failed to load YAML from {file_path}: {exc}")
        return []


async def code_gen(file_name,df, list_tasks=None):
    if list_tasks is None:
        list_tasks = []
    df_test = df
    agent = DataAnalystAgent(df_test)
    data_analysis_report = {}

    chart_intent_keywords = (
        "chart", "plot", "graph", "visual", "scatter", "bar", "line", "histogram",
        "distribution", "trend", "relationship", "correlation", "compare", "show",
    )
    for task in list_tasks:
        try:
            task_lower = task.lower()
            is_chart_task = any(keyword in task_lower for keyword in chart_intent_keywords)

            if is_chart_task:
                code_result = agent.code_service.generate_visualization_code(task+f" using the dataframe {agent.available_columns} and only using columns that exist in the dataframe. Always use plotly express for visualization and make sure to return the code in a variable named 'code' and the result of the code execution in a variable named 'result'.")
                generated_code = code_result.get("code")
                if generated_code:
                    exec_result = await run_in_threadpool(agent.executor.execute_with_healing, generated_code)
                    if exec_result.success:
                        code_result["success"] = True
                        code_result["result"] = exec_result.result
                        code_result["error"] = None
                    else:
                        code_result["success"] = False
                        code_result["result"] = None
                        code_result["error"] = exec_result.error
                generation_mode = "visualization_code"
            else:
                code_result = agent.code_service.generate_and_execute(task)
                generation_mode = "analysis_code"

            print("Generated Code:")
            print(code_result.get("code"))
            print("Execution Result:")
            print(code_result.get("result"))

            generated_code = code_result.get("code")
            chart_data = None
            chart_generation_status = "not_attempted"
            chart_generation_error = None

            if generated_code:
                try:
                    chart_data = generate_chart(df_test, generated_code)
                    if chart_data:
                        chart_generation_status = "generated_from_code"
                        logger.info("✅ Chart generation complete")
                    else:
                        chart_generation_status = "code_generated_no_chart"
                except Exception as chart_error:
                    chart_generation_status = "code_chart_failed"
                    chart_generation_error = str(chart_error)
                    logger.warning(
                        "Chart code failed for task; falling back to heuristic chart generation. Error: %s",
                        chart_error,
                    )
                    chart_data = generate_chart_from_query(df_test, task)
                    if chart_data:
                        chart_generation_status = "generated_from_fallback"
                    else:
                        chart_generation_status = "fallback_no_chart"
            else:
                logger.warning("No generated code returned for task: %s", task)
                chart_generation_status = "no_generated_code"

            execution_payload = code_result.get("result")
            if code_result.get("success") is False:
                execution_payload = {
                    "status": "failed",
                    "error": code_result.get("error"),
                }

            data_analysis_report[task] = {
                "generation_mode": generation_mode,
                "generated_code": generated_code,
                "execution_result": execution_payload,
                "chart_generated": bool(chart_data),
                "chart_generation_status": chart_generation_status,
                "chart_generation_error": chart_generation_error,
                # "chart_data": chart_data,
            }

            if not chart_data:
                logger.warning("No chart produced for task: %s", task)
            else:
                logger.info("Chart data for task '%s': %s", task, str(chart_data)[:200])  # Log a preview of the chart data
                fig = go.Figure(chart_data['data'])
                # 3. Add the annotation (using your specific coordinates and offsets)
                fig.add_annotation(
                    x=2, 
                    y=5, 
                    text=f"code: {task}",
                    showarrow=True,
                    arrowhead=1,
                    ax=-30, 
                    ay=-40,
                    font=dict(size=10, color="black"),
                    bgcolor="white",  # Optional: adds a background for better readability
                    bordercolor="gray"
                )
                fig.show()
        except Exception as task_error:
            logger.exception("Task failed and was skipped: %s", task_error)
            continue
    os.makedirs("/tmp/analysis", exist_ok=True)
    per_file_output_path = f"/tmp/analysis/{os.path.basename(file_path)}.json"
    per_file_payload = data_analysis_report
    with open(per_file_output_path, "w", encoding="utf-8") as output_file:
        json.dump(per_file_payload, output_file, indent=2)
    logger.info("Saved chart generation report to %s", per_file_output_path)


if __name__ == "__main__":
    chart_yaml_path = os.path.join(os.path.dirname(__file__), "chart_gen.yml")
    test_cases = load_test_cases_json(chart_yaml_path)
    data = {"test_cases": test_cases}

    # print(json.dumps(data, indent=2))
    
    for case in test_cases:
        file_path = case.get("file")
        tasks = [task.get("query") for task in case.get("tasks", []) if task.get("query")]
        if not file_path or not tasks:
            logger.warning("Skipping case with missing file or tasks: %s", case)
            continue

        if not os.path.exists(file_path):
            logger.error("Data file not found for case: %s", file_path)
            continue

        try:
            df = pd.read_csv(file_path)
            asyncio.run(code_gen(file_name=file_path, df=df, list_tasks=tasks))
        except Exception as e:
            logger.exception("Failed to process case with file %s: %s", file_path, e)
    