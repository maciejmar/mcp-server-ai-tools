# BGK AI MCP Server — Specyfikacja

Centralny serwer narzędzi AI dla Banku Gospodarstwa Krajowego. Udostępnia narzędzia do Jiry, Confluence, Grafany, Bitbucketa i infrastruktury (GPU, Docker, Ollama) przez protokół MCP (Model Context Protocol).

---

## Połączenie

| Parametr | Wartość |
|---|---|
| URL | `https://portal-ai.bank.com.pl/mcp` |
| Health check | `https://portal-ai.bank.com.pl/health` |
| Protokół | MCP Streamable HTTP (JSON-RPC 2.0 over SSE) |
| Autentykacja | Nagłówek `X-API-Key` |

### Wymagane nagłówki HTTP

```
Content-Type: application/json
Accept: application/json, text/event-stream
X-API-Key: <klucz-api>
```

---

## Inicjalizacja sesji

Każdy klient musi zacząć od wywołania `initialize`:

```bash
curl -X POST https://portal-ai.bank.com.pl/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-API-Key: TWOJ_KLUCZ" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "moj-agent", "version": "1.0"}
    }
  }'
```

Odpowiedź:
```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"bgk-ai-mcp","version":"1.27.0"},...}}
```

---

## Integracja z LangGraph / LangChain

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent

MCP_URL = "https://portal-ai.bank.com.pl/mcp"
MCP_API_KEY = "twoj-klucz"

async def create_agent(model):
    async with streamablehttp_client(
        MCP_URL,
        headers={"X-API-Key": MCP_API_KEY}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            agent = create_react_agent(model, tools)
            return agent
```

Instalacja:
```bash
pip install langchain-mcp-adapters mcp
```

---

## Integracja z Claude Code / Claude Desktop

W pliku konfiguracyjnym MCP:

```json
{
  "mcpServers": {
    "bgk-ai": {
      "url": "https://portal-ai.bank.com.pl/mcp",
      "headers": {
        "X-API-Key": "twoj-klucz"
      }
    }
  }
}
```

---

## Dostępne narzędzia (21)

### Jira (6 narzędzi)

#### `jira_search`
Wyszukuje tickety za pomocą JQL.

| Parametr | Typ | Opis |
|---|---|---|
| `jql` | string | Zapytanie JQL, np. `project = ZZ AND status = "In Progress"` |
| `max_results` | int | Maks. liczba wyników, 1–50 (domyślnie 20) |

Zwraca: `{ total, issues: [{key, summary, status, assignee, priority}] }`

---

#### `jira_get_issue`
Pobiera pełne szczegóły ticketa.

| Parametr | Typ | Opis |
|---|---|---|
| `issue_key` | string | Klucz ticketa, np. `ZZ-123` |

Zwraca: `{ key, summary, status, assignee, reporter, priority, issue_type, description, labels, created, updated, comments[] }`

---

#### `jira_create_issue`
Tworzy nowy ticket.

| Parametr | Typ | Opis |
|---|---|---|
| `project_key` | string | Klucz projektu, np. `ZZ` |
| `summary` | string | Tytuł ticketa |
| `description` | string | Opis |
| `issue_type` | string | `Task` / `Bug` / `Story` / `Epic` (domyślnie `Task`) |

Zwraca: `{ key, id, url }`

---

#### `jira_add_comment`
Dodaje komentarz do ticketa.

| Parametr | Typ | Opis |
|---|---|---|
| `issue_key` | string | Klucz ticketa |
| `comment` | string | Treść komentarza (obsługuje Jira markup) |

Zwraca: `{ success, comment_id, created }`

---

#### `jira_get_transitions`
Pobiera dostępne przejścia statusów. Wywołaj przed `jira_transition`.

| Parametr | Typ | Opis |
|---|---|---|
| `issue_key` | string | Klucz ticketa |

Zwraca: `{ transitions: [{id, name}] }`

---

#### `jira_transition`
Zmienia status ticketa.

| Parametr | Typ | Opis |
|---|---|---|
| `issue_key` | string | Klucz ticketa |
| `transition_name` | string | Nazwa przejścia, np. `In Progress`, `Done` |

Zwraca: `{ success, issue_key, new_status }`

---

### Confluence (4 narzędzia)

#### `confluence_search`
Wyszukuje strony za pomocą CQL.

| Parametr | Typ | Opis |
|---|---|---|
| `cql` | string | Zapytanie CQL, np. `text ~ "architektura" AND space.key = "AI"` |
| `max_results` | int | Maks. liczba wyników, 1–50 (domyślnie 10) |

Zwraca: `{ total, results: [{id, title, space_key, space_name, url, excerpt}] }`

---

#### `confluence_get_page`
Pobiera pełną treść strony.

| Parametr | Typ | Opis |
|---|---|---|
| `page_id` | string | Numeryczny ID strony, np. `123456` |

Zwraca: `{ id, title, space_key, version, url, parent_title, body_html }`

---

#### `confluence_create_page`
Tworzy nową stronę.

| Parametr | Typ | Opis |
|---|---|---|
| `space_key` | string | Klucz space, np. `AI`, `DEV` |
| `title` | string | Tytuł strony |
| `body` | string | Treść w Confluence Storage Format (XHTML) |
| `parent_id` | string | (opcjonalnie) ID strony nadrzędnej |

Zwraca: `{ id, title, url }`

---

#### `confluence_update_page`
Aktualizuje istniejącą stronę (całkowicie zastępuje treść).

| Parametr | Typ | Opis |
|---|---|---|
| `page_id` | string | ID strony |
| `title` | string | Nowy tytuł |
| `body` | string | Nowa treść w Confluence Storage Format |

Zwraca: `{ success, id, title, version, url }`

---

### Grafana (3 narzędzia)

#### `grafana_search_dashboards`
Wyszukuje dashboardy po nazwie lub tagu.

| Parametr | Typ | Opis |
|---|---|---|
| `query` | string | Fraza wyszukiwania, np. `gpu`, `api-latency` |

Zwraca: `{ dashboards: [{uid, title, url, folder_title, tags}] }`

---

#### `grafana_query_datasource`
Wykonuje zapytanie do datasource (Prometheus/Loki/SQL).

| Parametr | Typ | Opis |
|---|---|---|
| `datasource_uid` | string | UID datasource z konfiguracji Grafany |
| `query` | string | Zapytanie PromQL / LogQL / SQL |
| `from_time` | string | Początek zakresu, np. `now-1h`, `now-24h` (domyślnie `now-1h`) |
| `to_time` | string | Koniec zakresu (domyślnie `now`) |

Zwraca: serie danych z timestamps i wartościami.

---

#### `grafana_get_alerts`
Pobiera aktywne alerty z Alertmanagera.

| Parametr | Typ | Opis |
|---|---|---|
| `state` | string | `firing` / `pending` / `inactive` (domyślnie `firing`) |

Zwraca: `{ count, alerts: [{name, state, severity, labels, summary, description, starts_at}] }`

---

### Bitbucket (4 narzędzia)

#### `bitbucket_list_repos`
Lista repozytoriów w projekcie.

| Parametr | Typ | Opis |
|---|---|---|
| `project_key` | string | Klucz projektu, np. `AI`, `PORTAL` |

Zwraca: `{ total, repos: [{name, slug, clone_url_http, clone_url_ssh, default_branch, description}] }`

---

#### `bitbucket_get_file`
Pobiera zawartość pliku z repozytorium.

| Parametr | Typ | Opis |
|---|---|---|
| `project_key` | string | Klucz projektu |
| `repo_slug` | string | Slug repo, np. `bgk-mcp-server` |
| `file_path` | string | Ścieżka do pliku, np. `src/server.py` |
| `branch` | string | Gałąź lub commit SHA (domyślnie `main`) |

Zwraca: `{ content, file_path, branch }`

---

#### `bitbucket_list_prs`
Lista Pull Requestów.

| Parametr | Typ | Opis |
|---|---|---|
| `project_key` | string | Klucz projektu |
| `repo_slug` | string | Slug repozytorium |
| `state` | string | `OPEN` / `MERGED` / `DECLINED` (domyślnie `OPEN`) |

Zwraca: `{ total, pull_requests: [{id, title, author, source_branch, target_branch, reviewers[], created_date}] }`

---

#### `bitbucket_get_pr_diff`
Pobiera diff Pull Requesta w unified format.

| Parametr | Typ | Opis |
|---|---|---|
| `project_key` | string | Klucz projektu |
| `repo_slug` | string | Slug repozytorium |
| `pr_id` | int | Numeryczny ID Pull Requesta |

Zwraca: `{ pr_id, diff }`

---

### Infrastruktura (4 narzędzia)

#### `server_gpu_status`
Status GPU H100 na serwerze AI (nvidia-smi).

Bez parametrów.

Zwraca: `{ gpu_count, gpus: [{index, name, utilization_gpu_pct, memory_used_mb, memory_total_mb, temperature_c, power_draw_w}] }`

---

#### `server_container_status`
Status kontenerów Docker na serwerze.

| Parametr | Typ | Opis |
|---|---|---|
| `name_filter` | string | (opcjonalnie) Filtr po nazwie, np. `mcp`, `qdrant` |

Zwraca: `{ total, containers: [{name, status, image, ports, created, running_for}] }`

---

#### `ollama_list_models`
Lista modeli LLM dostępnych w Ollama.

Bez parametrów.

Zwraca: `{ count, models: [{name, size_gb, modified, digest}] }`

---

#### `ollama_model_info`
Szczegóły konkretnego modelu LLM.

| Parametr | Typ | Opis |
|---|---|---|
| `model_name` | string | Nazwa modelu, np. `llama3.1:70b`, `mistral:7b-instruct` |

Zwraca: `{ name, parameters, template, details, modelfile_excerpt }`

---

## Kody błędów

Wszystkie narzędzia zwracają błędy w formacie:
```json
{"error": "Opis błędu", "detail": "Szczegóły techniczne"}
```

Błędy MCP-level (JSON-RPC):
```json
{"jsonrpc": "2.0", "id": "server-error", "error": {"code": -32600, "message": "..."}}
```

| HTTP | Znaczenie |
|---|---|
| 200 | OK |
| 401 | Brak lub zły `X-API-Key` |
| 406 | Brak `Accept: application/json, text/event-stream` |
| 500 | Błąd serwera |

---

## Zmienne środowiskowe serwera

| Zmienna | Opis |
|---|---|
| `ANTHROPIC_API_KEY` | Klucz Anthropic (jeśli wymagany) |
| `JIRA_URL` | URL Jiry, np. `https://jira.bank.com.pl` |
| `JIRA_PAT` | Personal Access Token do Jiry |
| `CONFLUENCE_URL` | URL Confluence |
| `CONFLUENCE_PAT` | Personal Access Token do Confluence |
| `GRAFANA_URL` | URL Grafany |
| `GRAFANA_TOKEN` | Token API Grafany |
| `BITBUCKET_URL` | URL Bitbucketa |
| `BITBUCKET_PAT` | Personal Access Token do Bitbucketa |
| `OLLAMA_URL` | URL Ollamy, np. `http://localhost:11434` |
| `MCP_API_KEY` | Klucz API serwera (wysyłany przez klientów w `X-API-Key`) |
| `MCP_SERVER_PORT` | Port wewnętrzny kontenera (domyślnie `8000`) |
