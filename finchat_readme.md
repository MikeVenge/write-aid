# FinChat API Usage Guide

This document explains how to interact with the FinChat API based on the implementation patterns found in this codebase.

## API Configuration

The FinChat API is hosted at:
```python
finchat_url = "https://finchat-api.adgo.dev"
finchat_backoff_in_seconds = 5
```

## Core API Functions

### Generic HTTP Caller
```python
def call_remote(method, full_url, **kwargs):
    if method == "get":
        res = requests.get(full_url, params=kwargs)
    elif method in ["post", "put"]:
        res = requests.request(method, full_url, json=kwargs)
    else:
        raise ValueError(f"Unsupported method {method}")
    
    if res.status_code >= 400:
        raise ValueError(f"Failed to call {method} {full_url}:\nstatus:{res.status_code}\n\n{res.text}")
    return res.json()
```

### FinChat-Specific Wrapper
```python
def call_finchat(method, path, **kwargs):
    full_url = f"{finchat_url}{path}"
    return call_remote(method, full_url, **kwargs)
```

## Complete FinChat API Workflow

The typical workflow for using FinChat API involves these sequential steps:

### Step 1: Create a Session
```python
session = call_finchat(
    method="post",
    path="/api/v1/sessions/",
    client_id="parsec-backtesting",
    data_source="alpha_vantage",
)
session_id = session["id"]
```

### Step 2: Send a Chat Message
```python
call_finchat(
    method="post",
    path=f"/api/v1/chats/",
    session=session_id,
    message=magic_string,  # Your query/command
    use_live_cot=True,
)
```

### Step 3: Wait for Session to Complete
```python
def wait_till_idle(session_id, log_at_checks=5):
    check_count = 0
    while True:
        session = call_finchat(method="get", path=f"/api/v1/sessions/{session_id}/")
        check_count += 1
        session_status = session["status"]
        
        if session_status == "idle":
            break
            
        if check_count % log_at_checks == 0:
            log.info("Continuing to check session %s for idle. Currently %s. (Checked %s times)",
                    session_id, session_status, check_count)
        
        time.sleep(finchat_backoff_in_seconds)

# Usage
wait_till_idle(session_id=session_id)
```

### Step 4: Get the Result ID
```python
max_retries = 5
retries = 0
result_id = None

while retries < max_retries and result_id is None:
    chat_messages = call_finchat("get", f"/api/v1/chats/?session_id={session_id}")
    if chat_messages["results"]:
        latest_message = chat_messages["results"][-1]
        result_id = latest_message.get("result_id")
    if result_id is None:
        retries += 1
        log.warning("No valid result_id found. Retrying... (%d/%d)", retries, max_retries)
        time.sleep(15)

if result_id is None:
    log.error("Max retries reached. Failed to obtain a valid result_id")
    return None
```

### Step 5: Fetch the Full Analysis
```python
max_retries = 3
retries = 0
full_analysis = None

while retries < max_retries:
    try:
        full_analysis = call_finchat("get", f"/api/v1/results/{result_id}/")
        break  # Exit the loop if successful
    except Exception as e:
        retries += 1
        log.error("Attempt %d/%d failed: %s", retries, max_retries, str(e))
        if retries < max_retries:
            time.sleep(5)  # Wait before retrying

if full_analysis is None:
    log.error("Failed to fetch analysis after %d retries", max_retries)
    return None
```

## Available API Endpoints

Based on the codebase analysis, these endpoints are available:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/sessions/` | Create a new session |
| `GET` | `/api/v1/sessions/{session_id}/` | Get session status |
| `POST` | `/api/v1/chats/` | Send a message to a session |
| `GET` | `/api/v1/chats/?session_id={session_id}` | Get chat messages for a session |
| `GET` | `/api/v1/results/{result_id}/` | Get analysis results |
| `GET` | `/api/v1/companies/` | Get company data |
| `GET` | `/api/v1/earnings-calls/` | Get earnings calls data |

## Magic Strings (Commands)

FinChat uses structured "magic strings" as commands. Examples from the codebase:

### Write Aid Prompt
```python
magic_string = (
    f"cot write-aid-1 "
    f"$sentence:{sentence} "
    f"$paragraph:{paragraph} "
    f"$author:{author}"
)
```

Example: `"cot write-aid-1 $sentence:The market is volatile today $paragraph:Financial markets have been experiencing significant fluctuations... $author:John Smith"`

### Earnings Call Sentiment Analysis
```python
magic_string = (
    f"cot 4q-prior-earnings-call-sentiment-analysis-api-only-jan29 "
    f"$comp_ticker:{ticker.upper()} "
    f"$start_q:{prior_quarter} "
    f"$end_q:{current_quarter}"
)
```

Example: `"cot 4q-prior-earnings-call-sentiment-analysis-api-only-jan29 $comp_ticker:AAPL $start_q:2023Q4 $end_q:2024Q1"`

### Analyst Sentiment Analysis
```python
magic_string = (
    f"cot get-analyst-sentiment "
    f"$comp_ticker:{ticker.upper()} "
    f"$start_q:{prior_quarter} "
    f"$end_q:{current_quarter}"
)
```

Example: `"cot get-analyst-sentiment $comp_ticker:AAPL $start_q:2023Q4 $end_q:2024Q1"`

## Complete Examples

### Example 1: Write Aid Prompt

Here's a complete example of how to use the write-aid-1 prompt:

```python
import time
import logging
import requests

# Configuration
finchat_url = "https://finchat-api.adgo.dev"
finchat_backoff_in_seconds = 5

def get_writing_assistance(sentence, paragraph, author):
    """
    Get writing assistance using the write-aid-1 prompt.
    
    Args:
        sentence: The sentence to work with
        paragraph: The paragraph context
        author: The author name
    
    Returns:
        dict: Analysis results or None if failed
    """
    try:
        # Step 1: Create session
        session = call_finchat(
            method="post",
            path="/api/v1/sessions/",
            client_id="parsec-backtesting",
            data_source="alpha_vantage",
        )
        session_id = session["id"]
        
        # Step 2: Send writing aid request
        magic_string = (
            f"cot write-aid-1 "
            f"$sentence:{sentence} "
            f"$paragraph:{paragraph} "
            f"$author:{author}"
        )
        
        call_finchat(
            method="post",
            path=f"/api/v1/chats/",
            session=session_id,
            message=magic_string,
            use_live_cot=True,
        )
        
        # Step 3: Wait for completion
        wait_till_idle(session_id=session_id)
        
        # Step 4: Get result ID
        chat_messages = call_finchat("get", f"/api/v1/chats/?session_id={session_id}")
        if not chat_messages["results"]:
            return None
            
        latest_message = chat_messages["results"][-1]
        result_id = latest_message.get("result_id")
        
        if not result_id:
            return None
        
        # Step 5: Fetch analysis
        full_analysis = call_finchat("get", f"/api/v1/results/{result_id}/")
        
        return {
            "session_id": session_id,
            "result_id": result_id,
            "session_url": f"https://finchat.adgo.dev/?session_id={session_id}",
            "analysis": full_analysis
        }
        
    except Exception as e:
        logging.error(f"Failed to get writing assistance: {str(e)}")
        return None

# Usage
result = get_writing_assistance(
    sentence="The market is volatile today",
    paragraph="Financial markets have been experiencing significant fluctuations due to various economic factors including inflation concerns and geopolitical tensions.",
    author="John Smith"
)
if result:
    print(f"Writing assistance completed. Session URL: {result['session_url']}")
else:
    print("Writing assistance failed")
```

### Example 2: Stock Sentiment Analysis

Here's a complete example of how to get sentiment analysis for a stock:

```python
def analyze_stock_sentiment(ticker, current_quarter, prior_quarter):
    """
    Get sentiment analysis for a stock ticker.
    
    Args:
        ticker: Stock symbol (e.g., 'AAPL')
        current_quarter: Current quarter (e.g., '2024Q1')
        prior_quarter: Prior quarter (e.g., '2023Q4')
    
    Returns:
        dict: Analysis results or None if failed
    """
    try:
        # Step 1: Create session
        session = call_finchat(
            method="post",
            path="/api/v1/sessions/",
            client_id="parsec-backtesting",
            data_source="alpha_vantage",
        )
        session_id = session["id"]
        
        # Step 2: Send analysis request
        magic_string = (
            f"cot 4q-prior-earnings-call-sentiment-analysis-api-only-jan29 "
            f"$comp_ticker:{ticker.upper()} "
            f"$start_q:{prior_quarter} "
            f"$end_q:{current_quarter}"
        )
        
        call_finchat(
            method="post",
            path=f"/api/v1/chats/",
            session=session_id,
            message=magic_string,
            use_live_cot=True,
        )
        
        # Step 3: Wait for completion
        wait_till_idle(session_id=session_id)
        
        # Step 4: Get result ID
        chat_messages = call_finchat("get", f"/api/v1/chats/?session_id={session_id}")
        if not chat_messages["results"]:
            return None
            
        latest_message = chat_messages["results"][-1]
        result_id = latest_message.get("result_id")
        
        if not result_id:
            return None
        
        # Step 5: Fetch analysis
        full_analysis = call_finchat("get", f"/api/v1/results/{result_id}/")
        
        return {
            "session_id": session_id,
            "result_id": result_id,
            "session_url": f"https://finchat.adgo.dev/?session_id={session_id}",
            "analysis": full_analysis
        }
        
    except Exception as e:
        logging.error(f"Failed to analyze {ticker}: {str(e)}")
        return None

# Usage
result = analyze_stock_sentiment("AAPL", "2024Q1", "2023Q4")
if result:
    print(f"Analysis completed. Session URL: {result['session_url']}")
else:
    print("Analysis failed")
```

## Error Handling and Retry Logic

The API implementation includes robust error handling:

1. **Session Status Polling**: Continuously check session status until "idle"
2. **Result ID Retrieval**: Retry up to 5 times with 15-second delays
3. **Analysis Fetching**: Retry up to 3 times with exponential backoff
4. **HTTP Error Handling**: All API calls include status code validation

## Session URLs

After processing, you can access the interactive session at:
```
https://finchat.adgo.dev/?session_id={session_id}
```

This URL allows you to view the complete conversation and analysis in the FinChat web interface.

## Dependencies

Required Python packages:
```python
import requests
import time
import logging
import json
```

## Notes

- The API appears to be designed for financial analysis and earnings call sentiment analysis
- Sessions are stateful and maintain conversation context
- Results are accessible via both API and web interface
- The `use_live_cot=True` parameter enables chain-of-thought processing
- All API responses are in JSON format
