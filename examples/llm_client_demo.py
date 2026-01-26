#!/usr/bin/env python3
"""LLM Client usage examples for Clawd Bot."""

import asyncio
import os
from datetime import datetime, timedelta

# Mock the agent module for demonstration
# In production, just use: from agent.core.llm_client import LLMClient


async def example_1_basic_chat():
    """Example 1: Basic chat without tools."""
    print("=" * 60)
    print("Example 1: Basic Chat (Korean)")
    print("=" * 60)

    # Simulated usage
    print("""
from agent.core.llm_client import LLMClient

client = LLMClient()

response = await client.chat(
    messages=[
        {"role": "user", "content": "안녕! 오늘 날씨 어때?"}
    ],
    model="fast"  # Use fast model for simple queries
)

print(f"Provider: {response['provider']}")
print(f"Model: {response['model']}")
print(f"Response: {response['content']}")
    """)

    print("\nExpected output:")
    print("Provider: claude")
    print("Model: claude-3-5-haiku-20241022")
    print("Response: 안녕하세요! 저는 날씨 정보에 직접 접근할 수 없습니다...")


async def example_2_with_tools():
    """Example 2: Chat with tool calling."""
    print("\n" + "=" * 60)
    print("Example 2: Tool Calling (Health Data)")
    print("=" * 60)

    print("""
# Define tools for health data access
tools = [
    {
        "name": "get_sleep_data",
        "description": "Retrieve sleep data for a specific date",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_activity_summary",
        "description": "Get activity summary for a date range",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date": {"type": "string"}
            },
            "required": ["start_date", "end_date"]
        }
    }
]

# User asks about sleep
response = await client.chat(
    messages=[
        {"role": "user", "content": "어제 수면 점수가 어땠어?"}
    ],
    tools=tools,
    model="auto"  # Default balanced model
)

# Check if Claude wants to use a tool
if "tool_calls" in response:
    for call in response["tool_calls"]:
        print(f"Tool called: {call['name']}")
        print(f"Arguments: {call['input']}")

        # Execute the tool
        if call['name'] == 'get_sleep_data':
            sleep_data = get_sleep_data_from_db(call['input']['date'])
            print(f"Sleep score: {sleep_data['sleep_score']}")
    """)

    print("\nExpected flow:")
    print("1. User asks in Korean: '어제 수면 점수가 어땠어?'")
    print("2. Claude decides to use 'get_sleep_data' tool")
    print(f"3. Tool called with date: {(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}")
    print("4. Function executes and returns sleep data")
    print("5. Claude responds with the information in Korean")


async def example_3_multi_turn():
    """Example 3: Multi-turn conversation with context."""
    print("\n" + "=" * 60)
    print("Example 3: Multi-turn Conversation")
    print("=" * 60)

    print("""
# Maintain conversation history
messages = []

# Turn 1: User asks about sleep
messages.append({
    "role": "user",
    "content": "지난주 평균 수면 시간이 어땠어?"
})

response = await client.chat(messages, model="auto")
messages.append({
    "role": "assistant",
    "content": response["content"]
})

print(f"AI: {response['content']}")

# Turn 2: Follow-up question (context-aware)
messages.append({
    "role": "user",
    "content": "그럼 권장 시간보다 적은거야?"
})

response = await client.chat(messages, model="auto")
messages.append({
    "role": "assistant",
    "content": response["content"]
})

print(f"AI: {response['content']}")
    """)

    print("\nKey points:")
    print("• Conversation history enables context-aware responses")
    print("• Claude remembers previous messages in the conversation")
    print("• No need to repeat information")


async def example_4_model_selection():
    """Example 4: Smart model selection for different tasks."""
    print("\n" + "=" * 60)
    print("Example 4: Model Selection Strategy")
    print("=" * 60)

    print("""
# Fast model for simple lookups
response = await client.chat(
    messages=[{"role": "user", "content": "오늘 날짜가 언제야?"}],
    model="fast"  # claude-3-5-haiku (cheap & fast)
)

# Default model for normal conversations
response = await client.chat(
    messages=[{"role": "user", "content": "이번 주 운동 패턴 분석해줘"}],
    model="auto"  # claude-3-5-sonnet (balanced)
)

# Smart model for complex reasoning
response = await client.chat(
    messages=[{
        "role": "user",
        "content": "내 수면 패턴과 스트레스 수치 상관관계를 분석하고 "
                   "개선 방안을 제시해줘"
    }],
    model="smart"  # claude-3-opus (best reasoning)
)
    """)

    print("\nModel selection guide:")
    print("• fast/haiku → Simple queries, lookups, quick responses")
    print("• auto/sonnet → General conversations, moderate complexity")
    print("• smart/opus → Complex analysis, deep reasoning, debugging")


async def example_5_error_handling():
    """Example 5: Error handling and fallback."""
    print("\n" + "=" * 60)
    print("Example 5: Error Handling & Fallback")
    print("=" * 60)

    print("""
import logging

logger = logging.getLogger(__name__)

try:
    response = await client.chat(
        messages=[{"role": "user", "content": "건강 조언 부탁해"}],
        model="auto"
    )

    # Check which provider was used
    if response["provider"] == "claude":
        logger.info("Successfully used Claude API")
    elif response["provider"] == "openai":
        logger.warning("Used OpenAI fallback (Claude unavailable)")

except Exception as e:
    logger.error(f"Both providers failed: {e}")
    # Implement your fallback strategy
    # E.g., return a default response, queue for retry, etc.
    """)

    print("\nAutomatic fallback sequence:")
    print("1. Try Claude API")
    print("2. If Claude fails (rate limit/error) → Try OpenAI")
    print("3. If OpenAI also fails → Raise exception")
    print("\nYou can check response['provider'] to know which was used")


async def example_6_token_counting():
    """Example 6: Token counting for cost management."""
    print("\n" + "=" * 60)
    print("Example 6: Token Management")
    print("=" * 60)

    print("""
# Count tokens before sending (useful for rate limiting)
long_prompt = \"\"\"
사용자의 지난 30일 건강 데이터:
- 평균 수면: 7.2시간
- 평균 심박수: 68 BPM
- 스트레스 레벨: 중간
- 운동 빈도: 주 3회
...
(very long context)
\"\"\"

token_count = await client.count_tokens(long_prompt)

if token_count > 2000:
    print(f"Warning: Prompt is {token_count} tokens")
    # Summarize or chunk the prompt
    prompt = summarize_context(long_prompt)
else:
    prompt = long_prompt

response = await client.chat(
    messages=[{"role": "user", "content": prompt}],
    max_tokens=1024  # Limit response length
)
    """)

    print("\nToken management tips:")
    print("• Use count_tokens() before expensive operations")
    print("• Set max_tokens to control response length")
    print("• Summarize old conversation history")
    print("• Use fast model when possible to save costs")


async def example_7_real_world_integration():
    """Example 7: Real-world Telegram bot integration."""
    print("\n" + "=" * 60)
    print("Example 7: Telegram Bot Integration")
    print("=" * 60)

    print("""
from telegram import Update
from telegram.ext import ContextTypes
from agent.core.llm_client import LLMClient

client = LLMClient()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    \"\"\"Handle incoming Telegram messages with AI.\"\"\"
    user_message = update.message.text
    user_id = update.effective_user.id

    # Get or create conversation history
    if user_id not in context.user_data:
        context.user_data[user_id] = []

    messages = context.user_data[user_id]
    messages.append({"role": "user", "content": user_message})

    # Define available tools
    tools = [
        {
            "name": "get_health_summary",
            "description": "Get health summary from database",
            "input_schema": {...}
        }
    ]

    try:
        # Send to LLM
        response = await client.chat(
            messages=messages,
            tools=tools,
            model="auto"
        )

        # Handle tool calls
        if "tool_calls" in response:
            for call in response["tool_calls"]:
                result = await execute_tool(call["name"], call["input"])
                # Continue conversation with tool result...

        # Send response to user
        await update.message.reply_text(response["content"])

        # Save conversation
        messages.append({
            "role": "assistant",
            "content": response["content"]
        })

        # Trim old messages if too long
        if len(messages) > 20:
            messages = messages[-20:]

    except Exception as e:
        await update.message.reply_text(
            "죄송합니다. 일시적인 오류가 발생했습니다."
        )
        logging.error(f"LLM error: {e}")
    """)

    print("\nIntegration checklist:")
    print("✓ Maintain conversation history per user")
    print("✓ Define tools for data access")
    print("✓ Handle tool execution")
    print("✓ Implement error messages")
    print("✓ Trim conversation history periodically")
    print("✓ Use appropriate model for query complexity")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("LLM CLIENT USAGE EXAMPLES")
    print("=" * 60)

    await example_1_basic_chat()
    await example_2_with_tools()
    await example_3_multi_turn()
    await example_4_model_selection()
    await example_5_error_handling()
    await example_6_token_counting()
    await example_7_real_world_integration()

    print("\n" + "=" * 60)
    print("SETUP INSTRUCTIONS")
    print("=" * 60)
    print("""
1. Install dependencies:
   pip install -r clawd/requirements.txt

2. Set environment variables:
   export ANTHROPIC_API_KEY="sk-ant-your_key_here"
   export OPENAI_API_KEY="sk-your_key_here"  # Optional

3. Run the examples:
   python examples/llm_client_demo.py

4. Run tests:
   pytest tests/test_llm_client.py -v

For full documentation, see: agent/core/README.md
    """)


if __name__ == "__main__":
    asyncio.run(main())
