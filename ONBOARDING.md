# BGK AI MCP Server — Onboarding

Przewodnik dla członków zespołu chcących korzystać z centralnego serwera narzędzi AI.

---

## Uzyskanie klucza API

Skontaktuj się z administratorem serwera (zespół AI BGK) po klucz `X-API-Key`.  
Klucz jest indywidualny — nie udostępniaj go innym.

---

## Weryfikacja dostępu

Po otrzymaniu klucza sprawdź czy serwer odpowiada:

```bash
curl https://portal-ai.bank.com.pl/health
```

Oczekiwana odpowiedź: `{"status": "ok", "service": "bgk-ai-mcp"}`

---

## Sposób 1 — Claude Code CLI

Jeśli korzystasz z Claude Code na serwerze Red Hat, dodaj MCP server jedną komendą:

```bash
claude mcp add bgk-ai \
  --transport http \
  --url https://portal-ai.bank.com.pl/mcp \
  --header "X-API-Key: TWOJ_KLUCZ"
```

Albo ręcznie w pliku `~/.claude/claude.json`:

```json
{
  "mcpServers": {
    "bgk-ai": {
      "type": "http",
      "url": "https://portal-ai.bank.com.pl/mcp",
      "headers": {
        "X-API-Key": "TWOJ_KLUCZ"
      }
    }
  }
}
```

Po konfiguracji narzędzia są dostępne automatycznie w każdej sesji Claude Code —  
wystarczy zapytać np. _"sprawdź status GPU na serwerze"_ lub _"znajdź ticket ZZ-123 w Jirze"_.

---

## Sposób 2 — Agent Python (LangGraph / własny kod)

### Instalacja

```bash
pip install mcp langchain-mcp-adapters
```

### Minimalny przykład — wywołanie narzędzia

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "https://portal-ai.bank.com.pl/mcp"
API_KEY  = "TWOJ_KLUCZ"

async def main():
    async with streamablehttp_client(
        MCP_URL,
        headers={"X-API-Key": API_KEY}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # lista dostępnych narzędzi
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

            # przykładowe wywołanie — status GPU
            result = await session.call_tool("server_gpu_status", arguments={})
            print(result)

asyncio.run(main())
```

### Integracja z LangGraph

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic

MCP_URL = "https://portal-ai.bank.com.pl/mcp"
API_KEY  = "TWOJ_KLUCZ"

async def main():
    model = ChatAnthropic(model="claude-sonnet-4-6")

    async with streamablehttp_client(
        MCP_URL,
        headers={"X-API-Key": API_KEY}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools  = await load_mcp_tools(session)
            agent  = create_react_agent(model, tools)
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": "Sprawdź status GPU na serwerze"}]
            })
            print(result["messages"][-1].content)

asyncio.run(main())
```

---

## Dostępne narzędzia (21)

| Grupa | Narzędzia |
|---|---|
| **Jira** | `jira_search`, `jira_get_issue`, `jira_create_issue`, `jira_add_comment`, `jira_get_transitions`, `jira_transition` |
| **Confluence** | `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page` |
| **Grafana** | `grafana_search_dashboards`, `grafana_query_datasource`, `grafana_get_alerts` |
| **Bitbucket** | `bitbucket_list_repos`, `bitbucket_get_file`, `bitbucket_list_prs`, `bitbucket_get_pr_diff` |
| **Infrastruktura** | `server_gpu_status`, `server_container_status`, `ollama_list_models`, `ollama_model_info` |

Pełna dokumentacja parametrów i zwracanych danych: [MCP_SERVER_SPEC.md](MCP_SERVER_SPEC.md)

---

## Zasady korzystania

- Narzędzia zapisu (`jira_create_issue`, `confluence_create_page`, `confluence_update_page`, `jira_transition`) wykonują realne operacje — agent powinien potwierdzać z użytkownikiem przed wywołaniem
- `confluence_update_page` **całkowicie zastępuje treść strony** — zawsze pobierz istniejącą treść przed aktualizacją
- Przed `jira_transition` wywołaj `jira_get_transitions` — nie zgaduj nazw statusów
- Klucz API trzymaj w zmiennej środowiskowej, nie w kodzie:

```bash
export MCP_API_KEY="twoj-klucz"
```

```python
import os
API_KEY = os.environ["MCP_API_KEY"]
```

---

## Problemy i kontakt

| Problem | Rozwiązanie |
|---|---|
| `401 Unauthorized` | Sprawdź klucz API w nagłówku `X-API-Key` |
| `406 Not Acceptable` | Dodaj nagłówek `Accept: application/json, text/event-stream` |
| `{"error": "Błąd połączenia z Jirą"}` | Narzędzie dostępne, ale serwis zewnętrzny nieosiągalny |
| Serwer nie odpowiada | Sprawdź `https://portal-ai.bank.com.pl/health` |

Kontakt z administratorem: zespół AI BGK
