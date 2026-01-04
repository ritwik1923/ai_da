# Company GenAI API Integration Guide

## Overview

Your AI Data Analyst project now supports **two LLM providers**:
1. **OpenAI** (GPT-4, GPT-3.5, etc.)
2. **Company GenAI API** (ChatGPT4o, VertexGemini, Claude-Sonnet, etc.)

You can easily switch between them using environment variables.

---

## Quick Start

### 1. Configure Your API Key

Edit `backend/.env`:

```bash
# Choose your provider
LLM_PROVIDER=company

# Add your company API key
COMPANY_API_KEY=your-actual-api-key-here
COMPANY_MODEL=ChatGPT4o
COMPANY_USER_ID=your-email@motorolasolutions.com
```

### 2. Restart the Application

```bash
cd ~/ai_DA
sudo docker-compose down
sudo docker-compose up --build
```

### 3. Test It

Upload a CSV file and ask questions - it will now use your company's LLM API!

---

## Available Models

Configure using `COMPANY_MODEL` in `.env`:

| Model Name | Description |
|------------|-------------|
| `ChatGPT4o` | GPT-4 Omni (Recommended) |
| `ChatGPT4o-mini` | GPT-4 Omni Mini (Faster) |
| `VertexGemini` | Gemini 2.0 Flash |
| `Gemini-2_5-Flash` | Gemini 2.5 Flash |
| `Claude-Sonnet-4` | Claude Sonnet 4 |
| `OpenAI-ChatGPT-4_1` | ChatGPT 4.1 |
| `ChatGPT-5` | ChatGPT 5 |

---

## Configuration Options

### Environment Variables

```bash
# Provider Selection
LLM_PROVIDER=company          # or "openai"

# Company API Settings
COMPANY_API_KEY=xxx           # Your API key (required)
COMPANY_MODEL=ChatGPT4o       # Model to use
COMPANY_USER_ID=email@motorolasolutions.com  # Optional
COMPANY_BASE_URL=https://genai-service.stage.commandcentral.com/app-gateway
COMPANY_CLIENT_ID=ai-data-analyst

# OpenAI Settings (alternative)
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
```

---

## How It Works

### Architecture

```
User Query
    ↓
FastAPI Backend
    ↓
DataAnalystAgent
    ↓
LLM Provider Selection
    ├─→ OpenAI (ChatOpenAI)
    └─→ Company API (CompanyGenAILLM)
    ↓
Generate Code
    ↓
Execute & Return Results
```

### Custom LLM Wrapper

Located in `backend/app/utils/custom_llm.py`:

**Features:**
- ✅ LangChain-compatible interface
- ✅ Automatic session management
- ✅ Supports all company models
- ✅ Handles API errors gracefully
- ✅ Configurable temperature, max_tokens, etc.

**Key Classes:**
```python
CompanyGenAILLM       # Main wrapper for company API
OpenAICompatibleLLM   # Alternative OpenAI-compatible interface
```

---

## API Mapping

### Company API → LangChain

| Company API | LangChain Equivalent |
|-------------|---------------------|
| `prompt` | User message content |
| `system` | System message |
| `sessionId` | Managed automatically |
| `modelConfig.temperature` | `temperature` parameter |
| `modelConfig.max_tokens` | `max_tokens` parameter |
| `msg` (response) | AI message content |

### Request Flow

```python
# What happens internally:
{
    "model": "ChatGPT4o",
    "prompt": "Analyze sales data",
    "userId": "user@motorolasolutions.com",
    "modelConfig": {
        "temperature": 0,
        "max_tokens": 2000
    }
}
↓
Company API processes request
↓
{
    "status": true,
    "sessionId": "uuid-here",
    "msg": "Generated code response"
}
```

---

## Switching Between Providers

### To Use Company API (Testing)

```bash
# backend/.env
LLM_PROVIDER=company
COMPANY_API_KEY=your-key
COMPANY_MODEL=ChatGPT4o
```

### To Use OpenAI (Production)

```bash
# backend/.env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
```

**No code changes needed!** Just update `.env` and restart.

---

## Testing

### 1. Test Company API Integration

```bash
# In terminal
curl -X POST -H "x-msi-genai-api-key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     https://genai-service.stage.commandcentral.com/app-gateway/api/v2/chat \
     -d '{"model": "ChatGPT4o", "prompt": "Hello, test!"}'
```

### 2. Test in Your App

1. Start the application with `LLM_PROVIDER=company`
2. Upload `examples/sample_sales_data.csv`
3. Ask: "What are the total sales?"
4. Check logs to see company API being called

### 3. Verify in Logs

```bash
# You should see:
INFO: Using LLM Provider: company
INFO: Company Model: ChatGPT4o
```

---

## Troubleshooting

### Error: "Did not find openai_api_key"

**Solution:** You're still in OpenAI mode. Set:
```bash
LLM_PROVIDER=company
```

### Error: "401 Unauthorized"

**Solution:** Check your `COMPANY_API_KEY` is correct.

### Error: "Model not found"

**Solution:** Verify the model name. Use exact names like:
```bash
COMPANY_MODEL=ChatGPT4o
# NOT: COMPANY_MODEL=chatgpt4o
```

### Session Issues

The wrapper automatically manages sessions. Each conversation gets a unique `sessionId`.

---

## Cost Comparison

| Provider | Model | Cost per 1K tokens | Notes |
|----------|-------|-------------------|-------|
| Company API | ChatGPT4o | Internal billing | Tracked to your user ID |
| Company API | ChatGPT4o-mini | Internal billing | Faster, cheaper |
| OpenAI | gpt-4-turbo | ~$0.01-0.03 | Direct billing |

---

## Advanced Usage

### Custom Model Parameters

Edit `backend/app/agents/data_analyst.py`:

```python
return CompanyGenAILLM(
    api_key=settings.COMPANY_API_KEY,
    model=settings.COMPANY_MODEL,
    temperature=0.5,        # Adjust creativity
    max_tokens=4000,        # More for longer responses
    top_p=0.9,             # Nucleus sampling
    frequency_penalty=0.1   # Reduce repetition
)
```

### Using Different Models for Different Tasks

```python
# For code generation - use ChatGPT4o
code_llm = CompanyGenAILLM(model="ChatGPT4o")

# For quick queries - use mini version
quick_llm = CompanyGenAILLM(model="ChatGPT4o-mini")

# For multi-modal - use Gemini
vision_llm = CompanyGenAILLM(model="VertexGemini")
```

---

## Files Modified

1. **`backend/app/utils/custom_llm.py`** (NEW)
   - Custom LLM wrapper for company API
   
2. **`backend/app/core/config.py`**
   - Added company API settings
   
3. **`backend/app/agents/data_analyst.py`**
   - Added LLM provider selection logic
   
4. **`backend/.env`**
   - Added company API configuration

---

## Next Steps

1. **Get your API key** from your company's GenAI portal
2. **Update `.env`** with your credentials
3. **Restart containers**: `sudo docker-compose down && sudo docker-compose up --build`
4. **Test with sample data**
5. **Deploy to production** using OpenAI or keep using company API

---

## Support

For company API issues:
- Check the API documentation you provided
- Verify your API key is active
- Ensure your user ID is correct

For integration issues:
- Check `backend/app/utils/custom_llm.py`
- Review error logs in Docker output
- Test API directly with curl first

---

## Summary

✅ **Dual LLM Support**: Switch between OpenAI and Company API  
✅ **Easy Configuration**: Just change environment variables  
✅ **No Code Changes**: Works with existing code  
✅ **Session Management**: Automatic conversation tracking  
✅ **Multiple Models**: Support for ChatGPT, Gemini, Claude, etc.  
✅ **Production Ready**: Error handling and logging included  

You can now test with your company's API and switch to OpenAI later without any code changes!
