"""
Agent odpowiadający na pytania o składnię frameworków.

Pobiera dokumentację z Context7 MCP (npx @upstash/context7-mcp).
Opcjonalnie zapisuje odpowiedzi na Confluence przez bgk-ai-mcp.

Wymagania:
    pip install "anthropic[mcp]"
    npm install -g @upstash/context7-mcp   # lub działa przez npx bez instalacji

Zmienne środowiskowe:
    ANTHROPIC_API_KEY   - klucz API Anthropic
    BGK_MCP_URL         - URL Twojego serwera, np. http://localhost:8000/mcp
    MCP_API_KEY         - klucz API do bgk-ai-mcp
"""

import asyncio
import os

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# ── opcjonalnie, jeśli chcesz też narzędzia z bgk-ai-mcp ──────────────────
# from mcp.client.streamable_http import streamable_http_client
# BGK_MCP_URL = os.getenv("BGK_MCP_URL", "http://localhost:8000/mcp")
# BGK_API_KEY = os.getenv("MCP_API_KEY", "")
# ──────────────────────────────────────────────────────────────────────────


SYSTEM_PROMPT = """\
Jesteś ekspertem od składni komend i API różnych frameworków i bibliotek.

Gdy użytkownik pyta o framework lub bibliotekę:
1. Użyj `resolve-library-id` aby znaleźć identyfikator biblioteki w Context7.
2. Użyj `get-library-docs` z odpowiednim tematem (`topic`), np. "fixtures",
   "routing", "authentication", aby pobrać aktualną dokumentację.
3. Odpowiadaj wyłącznie na podstawie pobranej dokumentacji — nie korzystaj
   z wiedzy treningowej, bo może być nieaktualna.

Jeśli biblioteka nie istnieje w Context7, powiedz o tym i zasugeruj
sprawdzenie oficjalnej dokumentacji.
"""


async def ask_framework_question(question: str) -> None:
    """Zadaje pytanie agentowi i wypisuje odpowiedź na stdout."""
    client = anthropic.AsyncAnthropic()

    # Context7 uruchamiany lokalnie przez npx (stdio transport)
    ctx7_params = StdioServerParameters(
        command="npx",
        args=["-y", "@upstash/context7-mcp"],
    )

    async with stdio_client(ctx7_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            mcp_tools = [async_mcp_tool(t, session) for t in tools_result.tools]

            print(f"\n=== Pytanie: {question} ===\n")

            runner = client.beta.messages.tool_runner(
                model="claude-opus-4-7",
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=SYSTEM_PROMPT,
                tools=mcp_tools,
                messages=[{"role": "user", "content": question}],
            )

            async for message in runner:
                for block in message.content:
                    if block.type == "text" and block.text:
                        print(block.text)


async def main() -> None:
    questions = [
        "Jak używać pytest parametrize? Pokaż przykład z wieloma parametrami.",
        "Jak w FastAPI zdefiniować endpoint z path parameters i query params?",
        "Jak działa useEffect w React i kiedy go używać?",
    ]

    # Możesz też przyjmować pytanie interaktywnie:
    # question = input("Pytanie o framework: ")
    # await ask_framework_question(question)

    for q in questions[:1]:  # odkomentuj pętlę aby przetestować wszystkie
        await ask_framework_question(q)


if __name__ == "__main__":
    asyncio.run(main())
