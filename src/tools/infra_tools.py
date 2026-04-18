import asyncio
import logging
import httpx
from mcp.server.fastmcp import FastMCP
from src.clients.ollama_client import OllamaClient
from src.config import settings

logger = logging.getLogger(__name__)


def register_infra_tools(mcp: FastMCP, ollama_client: OllamaClient) -> None:
    """Rejestruje narzędzia infrastrukturalne w instancji MCP servera."""

    @mcp.tool()
    async def server_gpu_status() -> dict:
        """Sprawdza bieżący status GPU H100 na serwerze AI.

        Zwraca informacje o wykorzystaniu GPU, pamięci VRAM i temperaturze.
        Używa nvidia-smi do pobrania danych.

        Returns:
            Słownik z listą 'gpus', każdy zawiera: index, name, utilization_gpu_pct,
            memory_used_mb, memory_total_mb, temperature_c, power_draw_w.
            W przypadku braku nvidia-smi zwraca informację o błędzie.
        """
        logger.info("server_gpu_status called", extra={"tool": "server_gpu_status"})
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            if proc.returncode != 0:
                return {"error": "nvidia-smi zakończył się błędem", "detail": stderr.decode()}

            gpus = []
            for line in stdout.decode().strip().split("\n"):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 7:
                    continue
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "utilization_gpu_pct": float(parts[2]) if parts[2] != "[N/A]" else None,
                    "memory_used_mb": float(parts[3]) if parts[3] != "[N/A]" else None,
                    "memory_total_mb": float(parts[4]) if parts[4] != "[N/A]" else None,
                    "temperature_c": float(parts[5]) if parts[5] != "[N/A]" else None,
                    "power_draw_w": float(parts[6]) if parts[6] != "[N/A]" else None,
                })
            return {"gpu_count": len(gpus), "gpus": gpus}
        except FileNotFoundError:
            return {"error": "nvidia-smi nie jest dostępne na tym systemie"}
        except asyncio.TimeoutError:
            return {"error": "Timeout podczas pobierania statusu GPU"}

    @mcp.tool()
    async def server_container_status(name_filter: str | None = None) -> dict:
        """Sprawdza status kontenerów Docker działających na serwerze.

        Użyj gdy chcesz sprawdzić czy aplikacje AI są uruchomione i w jakim stanie.

        Args:
            name_filter: (opcjonalnie) Filtr po nazwie kontenera, np. 'mcp', 'qdrant'.
                         Jeśli nie podano, zwraca wszystkie kontenery.

        Returns:
            Słownik z listą 'containers', każdy zawiera: name, status, image,
            ports, created, running_for.
        """
        logger.info("server_container_status called", extra={
            "tool": "server_container_status", "name_filter": name_filter
        })
        try:
            cmd = [
                "docker", "ps", "-a",
                "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}\t{{.CreatedAt}}\t{{.RunningFor}}",
            ]
            if name_filter:
                cmd += ["--filter", f"name={name_filter}"]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode != 0:
                return {"error": "docker ps zakończył się błędem", "detail": stderr.decode()}

            containers = []
            for line in stdout.decode().strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 6:
                    continue
                containers.append({
                    "name": parts[0],
                    "status": parts[1],
                    "image": parts[2],
                    "ports": parts[3],
                    "created": parts[4],
                    "running_for": parts[5],
                })
            return {"total": len(containers), "containers": containers}
        except FileNotFoundError:
            return {"error": "Docker nie jest dostępny na tym systemie"}
        except asyncio.TimeoutError:
            return {"error": "Timeout podczas pobierania statusu kontenerów"}

    @mcp.tool()
    async def ollama_list_models() -> dict:
        """Wyświetla listę modeli LLM dostępnych w lokalnej instancji Ollama.

        Użyj gdy chcesz sprawdzić jakie modele są dostępne do użycia przez agenty AI.

        Returns:
            Słownik z listą 'models', każdy zawiera: name, size_gb, modified,
            quantization (jeśli dostępne w nazwie).
        """
        logger.info("ollama_list_models called", extra={"tool": "ollama_list_models"})
        try:
            data = await ollama_client.list_models()
            models = []
            for m in data.get("models", []):
                size_bytes = m.get("size", 0)
                models.append({
                    "name": m.get("name"),
                    "size_gb": round(size_bytes / (1024 ** 3), 2) if size_bytes else None,
                    "modified": m.get("modified_at", ""),
                    "digest": m.get("digest", "")[:12] if m.get("digest") else "",
                })
            return {"count": len(models), "models": models}
        except httpx.HTTPStatusError as e:
            return {"error": f"Ollama zwróciła błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Ollama", "detail": str(e)}

    @mcp.tool()
    async def ollama_model_info(model_name: str) -> dict:
        """Pobiera szczegółowe informacje o konkretnym modelu LLM z Ollamy.

        Użyj gdy chcesz poznać parametry modelu, rozmiar kontekstu lub typ kwantyzacji.

        Args:
            model_name: Nazwa modelu, np. 'llama3.1:70b', 'mistral:7b-instruct'.

        Returns:
            Słownik z parametrami modelu: modelfile (fragment), parameters, template,
            details (family, parameter_size, quantization_level).
        """
        logger.info("ollama_model_info called", extra={"tool": "ollama_model_info", "model_name": model_name})
        try:
            data = await ollama_client.model_info(model_name)
            return {
                "name": model_name,
                "parameters": data.get("parameters", ""),
                "template": data.get("template", ""),
                "details": data.get("details", {}),
                "modelfile_excerpt": (data.get("modelfile", "") or "")[:500],
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Ollama zwróciła błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Ollama", "detail": str(e)}
