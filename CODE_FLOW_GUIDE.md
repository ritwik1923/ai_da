# 🔄 Complete Code Flow & LLM Query Guide

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Step-by-Step Flow](#step-by-step-flow)
3. [LLM Query Process](#llm-query-process)
4. [How to Get Better Responses](#how-to-get-better-responses)
5. [Troubleshooting](#troubleshooting)

---

## System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   React     │────▶│   FastAPI    │────▶│   LangChain  │
│  Frontend   │     │   Backend    │     │    Agent     │
└─────────────┘     └──────────────┘     └──────────────┘
                            │                     │
                            ▼                     ▼
                    ┌──────────────┐     ┌──────────────┐
                    │  PostgreSQL  │     │     LLM      │
                    │   Database   │     │ (Company API)│
                    └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │    Tools     │
                                         │ - DataFrame  │
                                         │ - Execute    │
                                         │ - Analyze    │
                                         └──────────────┘
```

---

## Step-by-Step Flow

### Phase 1: User Input → Frontend
```javascript
// File: frontend/src/services/chatService.ts

1. User types: "What is the total sales?"
2. Frontend captures input in ChatPage.tsx
3. Calls sendMessage() function:

async sendMessage(sessionId: string, message: string, fileId?: number) {
  const response = await api.post('/api/chat/message', {
    session_id: sessionId,
    message: message,
    file_id: fileId
  });
  return response.data;
}
```

### Phase 2: Backend Receives Request
```python
# File: backend/app/api/chat.py

@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    
    # Step 1: Load CSV/Excel file into pandas DataFrame
    df = pd.read_csv(file.file_path)
    
    # Step 2: Get conversation history for context
    conversation_memory = [
        {"role": msg.role, "content": msg.content}
        for msg in previous_messages
    ]
    
    # Step 3: Create DataAnalystAgent with DataFrame + Memory
    agent = DataAnalystAgent(df, conversation_memory)
    
    # Step 4: Analyze the query
    result = agent.analyze(request.message)  # ← MAIN PROCESSING HERE
    
    # Step 5: Save to database and return
    return ChatResponse(response=result["answer"])
```

### Phase 3: DataAnalystAgent Processing
```python
# File: backend/app/agents/data_analyst.py

class DataAnalystAgent:
    def __init__(self, df, conversation_memory):
        # 1. Load DataFrame
        self.df = df
        
        # 2. Initialize LLM (Company GenAI or OpenAI)
        self.llm = self._initialize_llm()
        
        # 3. Create conversation memory
        self.memory = ConversationBufferMemory()
        
        # 4. Create tools (3 tools available)
        self.tools = self._create_tools()
        
        # 5. Create LangChain Agent Executor
        self.agent = self._create_agent()
```

#### Tools Available to Agent:
```python
1. get_dataframe_info(query: str) → str
   - Shows df.info(), df.head(), df.describe()
   - Used to understand data structure

2. execute_pandas_code(code: str) → str
   - Executes Python/Pandas code safely
   - Returns JSON result
   - Uses RestrictedPython for security

3. analyze_column(column_name: str) → str
   - Analyzes a specific column
   - Returns stats, unique values, null count
```

### Phase 4: LangChain Agent Executor
```python
def analyze(self, query: str) -> Dict[str, Any]:
    # This is where the magic happens!
    
    # 1. Agent receives query: "What is the total sales?"
    response = self.agent.invoke({"input": query})
    
    # 2. Agent Executor does this internally:
    #    a. Sends query + tools to LLM
    #    b. LLM decides which tool to use
    #    c. Agent executes the tool
    #    d. LLM sees the result
    #    e. LLM generates final answer
    
    # 3. Return formatted response
    return {
        "answer": response["output"],
        "generated_code": code,
        "success": True
    }
```

---

## LLM Query Process (The Brain)

### How the LLM Receives Information

```python
# The prompt sent to LLM looks like this:

SYSTEM MESSAGE:
"""
You are an expert data analyst AI assistant.

When a user asks a question:
1. If needed, use get_dataframe_info to understand data structure
2. Write Python/Pandas code to answer the question
3. EXECUTE the code using execute_pandas_code tool
4. Analyze the execution result
5. Provide a clear final answer with actual numbers

CRITICAL: Actually execute code, don't just plan it!

Tools available:
- get_dataframe_info(query)
- execute_pandas_code(code)
- analyze_column(column_name)

The dataframe 'df' is already loaded.
"""

CHAT HISTORY:
[Previous conversation context]

USER INPUT:
"What is the total sales?"

AGENT SCRATCHPAD:
[This is where the agent tracks its thinking and tool calls]
```

### Internal LLM Decision Process

```
LLM Receives:
- System instructions
- Available tools
- User query: "What is the total sales?"
- DataFrame context

LLM Thinks:
"I need to:
1. Find the 'sales' column
2. Sum all values
3. Return the result"

LLM Action 1: Check data structure
Tool Call: get_dataframe_info("")
Result: "Columns: product, sales, region, date"

LLM Action 2: Execute code
Tool Call: execute_pandas_code("result = df['sales'].sum()")
Result: {"type": "scalar", "value": 3130}

LLM Action 3: Generate answer
Final Output: "The total sales is $3,130"
```

### Actual API Call to Company GenAI

```python
# File: backend/app/utils/custom_llm.py

class CompanyGenAILLM(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None):
        # Convert LangChain messages to Company API format
        formatted_messages = [
            {
                "role": "user" if msg.type == "human" else "assistant",
                "content": msg.content
            }
            for msg in messages
        ]
        
        # Make HTTP request to Company GenAI API
        response = requests.post(
            f"{self.base_url}/chat",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-User-ID": self.user_id,
                "X-Client-ID": self.client_id
            },
            json={
                "messages": formatted_messages,
                "model": self.model,  # "ChatGPT4o"
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }
        )
        
        # Extract response
        content = response.json()["choices"][0]["message"]["content"]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
```

---

## How to Get Better Responses

### 1. **Clear, Specific Questions**

❌ **Bad**: "Analyze this"
✅ **Good**: "What is the total sales by region?"

❌ **Bad**: "Show me something interesting"
✅ **Good**: "What are the top 3 products by revenue?"

### 2. **Use Business Language**

✅ **Good Examples**:
- "What's the average order value?"
- "Which region has the highest sales?"
- "Show me sales trends over time"
- "What percentage of sales come from Laptops?"

### 3. **Break Complex Questions**

❌ **Bad**: "Show me total sales by region and product, filtered for discounts > 10%, grouped by quarter, with averages"

✅ **Good** (Sequential):
1. "What regions are in the data?"
2. "What's the total sales for the North region?"
3. "For North region, what's the breakdown by product?"

### 4. **Leverage Conversation Memory**

The agent remembers context! Use follow-up questions:

```
User: "What is the total sales?"
Agent: "The total sales is $3,130"

User: "What about by region?"  ← Agent remembers we're talking about sales
Agent: "North: $2,700, South: $55, East: $75, West: $300"

User: "Which one is highest?"  ← Agent remembers we're comparing regions
Agent: "North region has the highest sales at $2,700"
```

### 5. **Prompt Engineering in System Message**

The system prompt is KEY to good responses. Current prompt structure:

```python
system_message = """
You are an expert data analyst AI assistant.

When a user asks a question:
1. If needed, use get_dataframe_info to understand data structure
2. Write Python/Pandas code to answer the question
3. EXECUTE the code using execute_pandas_code tool  ← CRITICAL
4. Analyze the execution result
5. Provide a clear final answer with actual numbers

CRITICAL: Actually execute code, don't just plan it!

Example:
User: "What is the total sales?"
You: [Use execute_pandas_code with "result = df['sales'].sum()"]
You: "The total sales is $3,130"  ← Actual number, not "I'll calculate it"
"""
```

**Why this works:**
- ✅ Clear step-by-step instructions
- ✅ Explicit example showing expected behavior
- ✅ CRITICAL warnings to prevent planning-only responses
- ✅ Emphasizes actual execution over planning

### 6. **Optimize LLM Parameters**

```python
# Current settings in config.py
COMPANY_MODEL = "ChatGPT4o"  # Best for reasoning
temperature = 0              # Deterministic, no creativity
max_tokens = 2000           # Enough for code + explanation

# For better code generation:
temperature = 0        # More precise, less random
max_tokens = 2000      # Allows complex code

# For creative analysis:
temperature = 0.3      # Slightly more creative
max_tokens = 1500      # Shorter responses
```

---

## Query Optimization Patterns

### Pattern 1: Aggregation Queries
```python
# User asks: "What is the total sales?"

# Good prompt encourages:
code = "result = df['sales'].sum()"

# Returns:
{"type": "scalar", "value": 3130}

# Agent says:
"The total sales is $3,130"
```

### Pattern 2: Grouping Queries
```python
# User asks: "Show sales by region"

# Agent generates:
code = "result = df.groupby('region')['sales'].sum()"

# Returns:
{
  "type": "series",
  "data": {"North": 2700, "South": 55, "East": 75, "West": 300}
}

# Agent formats nicely:
"Sales by region:
- North: $2,700
- South: $55
- East: $75
- West: $300"
```

### Pattern 3: Filtering Queries
```python
# User asks: "What products sold for more than $100?"

# Agent generates:
code = "result = df[df['sales'] > 100][['product', 'sales']]"

# Returns:
{
  "type": "dataframe",
  "data": [
    {"product": "Laptop", "sales": 1200},
    {"product": "Monitor", "sales": 300},
    {"product": "Laptop", "sales": 1500}
  ]
}
```

---

## Code Execution Safety (RestrictedPython)

### How Safe Execution Works

```python
# File: backend/app/utils/code_executor.py

def safe_execute_pandas_code(code: str, df: pd.DataFrame):
    # 1. Create restricted environment
    safe_locals = {
        'df': df,                    # DataFrame available
        'pd': pd,                    # Pandas library
        '_getitem_': _getitem_,      # Allow df['column']
        '_getattr_': safer_getattr,  # Allow df.column
        '__builtins__': safe_builtins # Restricted functions
    }
    
    # 2. Compile with RestrictedPython
    byte_code = compile_restricted(code, '<inline>', 'exec')
    
    # 3. Execute safely
    exec(byte_code, safe_locals)
    
    # 4. Extract result
    result = safe_locals.get('result')
    
    # 5. Convert to JSON-serializable format
    if isinstance(result, pd.DataFrame):
        return {"type": "dataframe", "data": result.to_dict('records')}
    elif isinstance(result, (int, float, np.integer, np.floating)):
        return {"type": "scalar", "value": float(result)}
```

**What's Blocked:**
- ❌ File system access (`open()`, `os`)
- ❌ Network requests (`requests`, `urllib`)
- ❌ System commands (`subprocess`, `eval()`)
- ❌ Import arbitrary modules

**What's Allowed:**
- ✅ Pandas operations
- ✅ NumPy operations
- ✅ DataFrame manipulation
- ✅ Safe built-in functions (len, sum, max, min)

---

## Troubleshooting Common Issues

### Issue 1: Agent Doesn't Execute Code

**Symptom**: Returns "I'll execute the code" but no result

**Cause**: LLM stops after planning, doesn't use tools

**Fix**:
```python
# In system prompt, add:
"CRITICAL: Do NOT just say 'Let me execute' - 
ACTUALLY execute using execute_pandas_code tool"

# In AgentExecutor:
early_stopping_method="generate"  # Forces final answer
return_intermediate_steps=True    # Tracks tool usage
```

### Issue 2: Wrong Column Names

**Symptom**: Error "column not found"

**Cause**: Agent guesses column names without checking

**Fix**:
```python
# Agent should first use:
get_dataframe_info("")  # See actual columns

# Then generate code with correct names
```

### Issue 3: Hallucinated Data

**Symptom**: Agent makes up data that doesn't exist

**Fix**:
```python
# System prompt includes:
"ONLY use data from the DataFrame. 
If a column doesn't exist, say so clearly.
Do NOT make up fake data."

# Test with:
"Show me customer emails"  # Column doesn't exist
Expected: "The 'email' column is not in the dataset"
NOT: Fake emails like "john@example.com"
```

### Issue 4: Slow Responses

**Cause**: Multiple LLM calls, inefficient code

**Optimization**:
```python
# 1. Use faster model
COMPANY_MODEL = "ChatGPT4o"  # Faster than GPT-4

# 2. Reduce max_tokens for simple queries
max_tokens = 1000  # Instead of 2000

# 3. Cache dataframe info
# Don't call get_dataframe_info every time
```

---

## Performance Monitoring

### Track Agent Decisions

```python
# Enable verbose mode to see thinking
AGENT_VERBOSE = True

# Logs will show:
> Entering new AgentExecutor chain...
Thought: I need to check the data structure
Action: get_dataframe_info
Action Input: ""
Observation: [DataFrame info]
Thought: Now I'll calculate total sales
Action: execute_pandas_code
Action Input: result = df['sales'].sum()
Observation: {"type": "scalar", "value": 3130}
Final Answer: The total sales is $3,130
> Finished chain.
```

### Measure Response Time

```python
import time

start = time.time()
result = agent.analyze(query)
duration = time.time() - start

print(f"Query took {duration:.2f} seconds")
# Typical: 2-5 seconds per query
```

---

## Best Practices Summary

### ✅ DO:
1. **Clear Questions**: "What is X?" not "Tell me about stuff"
2. **Use Examples**: Include example in system prompt
3. **Enforce Execution**: Make LLM actually run code
4. **Handle Errors**: Wrap in try/except, return friendly messages
5. **Validate Output**: Check if result makes sense
6. **Use Memory**: Leverage conversation context
7. **Test Hallucination**: Ask for non-existent columns

### ❌ DON'T:
1. **Vague Queries**: "Analyze this dataset"
2. **Skip Validation**: Trust LLM without checking
3. **Allow Unsafe Code**: Always use RestrictedPython
4. **Ignore Errors**: Show user-friendly error messages
5. **Forget Context**: Use conversation memory
6. **Over-complicate**: Break complex queries into steps

---

## Key Files Reference

```
Backend Flow:
├── app/api/chat.py              # Entry point
├── app/agents/data_analyst.py   # Main agent logic
├── app/utils/custom_llm.py      # Company API wrapper
├── app/utils/code_executor.py   # Safe execution
└── app/core/config.py           # Settings

Frontend Flow:
├── src/pages/ChatPage.tsx       # UI
├── src/services/chatService.ts  # API calls
└── src/services/api.ts          # HTTP client
```

---

## Summary

**The Complete Journey:**
1. User asks question → Frontend
2. Frontend sends to `/api/chat/message` → Backend
3. Backend loads CSV into DataFrame
4. Creates DataAnalystAgent with DataFrame + Memory
5. Agent sends to LangChain Agent Executor
6. Executor sends to LLM with tools + context
7. LLM decides to use `execute_pandas_code` tool
8. Tool runs code safely in RestrictedPython
9. Result goes back to LLM
10. LLM formats nice answer
11. Answer goes to user

**Critical Success Factors:**
- ✅ Strong system prompt that enforces execution
- ✅ Proper tool definitions with clear descriptions
- ✅ Safe code execution environment
- ✅ Conversation memory for context
- ✅ Error handling at every layer
- ✅ User-friendly responses with actual data

This architecture ensures:
- 🔒 **Security**: RestrictedPython sandbox
- 🎯 **Accuracy**: Tools provide real data, not hallucinations
- 💬 **Context**: Memory tracks conversation
- ⚡ **Performance**: Efficient tool usage
- 🔧 **Flexibility**: Dual LLM provider support
