import asyncio
import json
import logging
import re
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
            params: dict = {"all": "1"}
            if name_filter:
                params["filters"] = json.dumps({"name": [name_filter]})

            transport = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
            async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=15.0) as client:
                response = await client.get("/containers/json", params=params)
            if response.status_code != 200:
                return {"error": f"Docker API returned {response.status_code}"}

            containers = []
            for c in response.json():
                names = [n.lstrip("/") for n in c.get("Names", [])]
                ports = ", ".join(
                    f"{p['PublicPort']}:{p['PrivatePort']}/{p['Type']}"
                    for p in c.get("Ports", []) if p.get("PublicPort")
                )
                containers.append({
                    "name": names[0] if names else c.get("Id", "")[:12],
                    "status": c.get("Status", ""),
                    "image": c.get("Image", ""),
                    "ports": ports,
                    "created": c.get("Created", ""),
                    "running_for": c.get("Status", ""),
                })
            return {"total": len(containers), "containers": containers}
        except Exception as exc:
            return {"error": f"Błąd połączenia z Docker socket: {exc}"}

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

    @mcp.tool()
    async def server_system_info() -> dict:
        """Pobiera informacje systemowe hosta przez Docker socket: CPU, RAM, wersja Docker, OS."""
        logger.info("server_system_info called", extra={"tool": "server_system_info"})
        try:
            transport = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
            async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=15.0) as client:
                response = await client.get("/info")
            if response.status_code != 200:
                return {"error": f"Docker API returned {response.status_code}"}
            data = response.json()
            return {
                "cpus": data.get("NCPU"),
                "memory_total_gb": round(data.get("MemTotal", 0) / (1024 ** 3), 2),
                "docker_version": data.get("ServerVersion"),
                "kernel_version": data.get("KernelVersion"),
                "os": data.get("OperatingSystem"),
                "storage_driver": data.get("Driver"),
                "containers": {
                    "running": data.get("ContainersRunning"),
                    "paused": data.get("ContainersPaused"),
                    "stopped": data.get("ContainersStopped"),
                },
                "images_count": data.get("Images"),
            }
        except Exception as exc:
            return {"error": f"System info error: {exc}"}

    @mcp.tool()
    async def container_inspect(container_name: str) -> dict:
        """Pobiera konfiguracje kontenera: limity zasobow, restart policy, zmienne srodowiskowe.

        Args:
            container_name: Nazwa kontenera Docker, np. '''bgk-mcp-server'''.
        """
        logger.info("container_inspect called", extra={"tool": "container_inspect", "container": container_name})
        try:
            transport = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
            async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=15.0) as client:
                response = await client.get(f"/containers/{container_name}/json")
            if response.status_code == 404:
                return {"error": f"Container not found: {container_name}"}
            if response.status_code != 200:
                return {"error": f"Docker API returned {response.status_code}"}
            data = response.json()
            host_cfg = data.get("HostConfig", {})
            state = data.get("State", {})
            config = data.get("Config", {})
            sensitive_re = re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_\-]?key|pat)=")
            env_redacted = []
            for e in config.get("Env", []):
                if sensitive_re.search(e):
                    env_redacted.append(e.split("=", 1)[0] + "=[REDACTED]")
                else:
                    env_redacted.append(e)
            mem_limit = host_cfg.get("Memory", 0)
            cpu_quota = host_cfg.get("CpuQuota", 0)
            cpu_period = host_cfg.get("CpuPeriod", 0) or 100000
            return {
                "name": container_name,
                "image": config.get("Image"),
                "status": state.get("Status"),
                "health": state.get("Health", {}).get("Status") if state.get("Health") else None,
                "restart_count": state.get("RestartCount", 0),
                "restart_policy": host_cfg.get("RestartPolicy", {}).get("Name"),
                "memory_limit_mb": round(mem_limit / (1024 ** 2), 1) if mem_limit else "unlimited",
                "cpu_limit": round(cpu_quota / cpu_period, 2) if cpu_quota > 0 else "unlimited",
                "environment": env_redacted,
                "mounts": [
                    {"source": m.get("Source"), "destination": m.get("Destination"), "mode": m.get("Mode")}
                    for m in data.get("Mounts", [])
                ],
            }
        except Exception as exc:
            return {"error": f"Container inspect error: {exc}"}

    @mcp.tool()
    async def docker_system_df() -> dict:
        """Pokazuje zuzycie dysku przez Docker: obrazy, woluminy, zatrzymane kontenery."""
        logger.info("docker_system_df called", extra={"tool": "docker_system_df"})
        try:
            transport = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
            async with httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=30.0) as client:
                response = await client.get("/system/df")
            if response.status_code != 200:
                return {"error": f"Docker API returned {response.status_code}"}
            data = response.json()

            def to_gb(b):
                return round(b / (1024 ** 3), 2)

            images = sorted(
                [{"tag": (i.get("RepoTags") or ["<none>"])[0], "size_gb": to_gb(i.get("Size", 0))}
                 for i in data.get("Images", [])],
                key=lambda x: -x["size_gb"],
            )[:20]
            volumes = sorted(
                [{"name": v.get("Name"), "size_gb": to_gb((v.get("UsageData") or {}).get("Size", 0) or 0)}
                 for v in data.get("Volumes", [])],
                key=lambda x: -x["size_gb"],
            )[:10]
            stopped_count = sum(1 for c in data.get("Containers", []) if c.get("State") != "running")
            return {
                "total_images_gb": to_gb(sum(i.get("Size", 0) for i in data.get("Images", []))),
                "images": images,
                "volumes": volumes,
                "stopped_containers_reclaimable": stopped_count,
            }
        except Exception as exc:
            return {"error": f"Docker system df error: {exc}"}
