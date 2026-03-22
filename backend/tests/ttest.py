import pandas as pd
import time
import matplotlib.pyplot as plt
import os, sys
import plotly.express as px
# Importing from 'app' directly as it is a top-level directory in your backend
# from app.agents.data_analyst_v2 import DataAnalystAgent
# from app.models.models import AnalysisResult
# from app.schemas.schemas import AnalysisResponse

# Use os.path.expanduser to ensure the '~' is recognized correctly
file_path = os.path.expanduser("~/Downloads/products-100.csv")
df = pd.read_csv(file_path)
# query = "What is the average price of products?"
result = df.groupby('Availability')['Price'].mean().reset_index()
fig = px.line(result, x='Availability', y='Price', title='Average Price by Availability Status')
fig.show()
# # Added 'query' as a parameter to match your function call
# def test_agent_analysis(query):
#     start_time = time.time()
#     result = agent.analyze(query)
#     execution_time = int((time.time() - start_time) * 1000)  # milliseconds
    
#     # Save analysis result
#     analysis = AnalysisResult(
#         file_id=3030,
#         query=query,
#         generated_code=result.get("generated_code", ""),
#         result_data=result.get("execution_result"),
#         chart_config=result.get("chart_data"),
#         execution_time=execution_time
#     )
    
#     print(f"Analysis result: {result.get('answer', 'No answer returned')}")
    
#     # Create the response object
#     response = AnalysisResponse(
#         query=query,
#         answer=result.get("answer", ""),
#         generated_code=result.get("generated_code", ""),
#         result_data=result.get("execution_result"),
#         chart_data=result.get("chart_data"),
#         execution_time=execution_time
#     )
#     print(response.json())

# # Execute
# if __name__ == "__main__":
#     test_agent_analysis(query=query)