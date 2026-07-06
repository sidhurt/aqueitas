import os
import sys
import subprocess
import time
import json
from pathlib import Path
import typer
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

# Configure paths based on global installation structure
CLI_DIR = Path(__file__).parent.absolute()
ROOT_DIR = CLI_DIR.parent.absolute()
BRAIN_DIR = ROOT_DIR / "brain"
VENV_DIR = BRAIN_DIR / "venv"

app = typer.Typer(
    name="Aqueitas",
    help="Aqueitas Engineering OS — CLI",
    add_completion=False,
    no_args_is_help=True
)
console = Console()

@app.command()
def start():
    """Start Vault (Docker) and Brain (FastAPI)"""
    console.print(Panel.fit("[bold cyan]⚡ Launching the Sovereign Engine...[/bold cyan]"))
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Task 1: Vault
        task_vault = progress.add_task("[blue]Starting Vault (Docker Compose)...", total=None)
        
        try:
            subprocess.run(
                ["docker-compose", "up", "-d"], 
                cwd=ROOT_DIR, 
                check=True, 
                capture_output=True, 
                text=True
            )
            progress.update(task_vault, completed=True, description="[green]Vault is up.[/green]")
        except subprocess.CalledProcessError as e:
            progress.stop()
            console.print("[bold red]Failed to start Vault (Docker). Is Docker Desktop running?[/bold red]")
            console.print(f"[red]{e.stderr}[/red]")
            raise typer.Exit(1)
        except FileNotFoundError:
            progress.stop()
            console.print("[bold red]Docker Compose not found. Please install Docker.[/bold red]")
            raise typer.Exit(1)
            
        # Task 2: Brain
        task_brain = progress.add_task("[blue]Launching Intelligence Brain (FastAPI)...", total=None)
        
        uvicorn_exec = VENV_DIR / "Scripts" / "uvicorn.exe" if os.name == "nt" else VENV_DIR / "bin" / "uvicorn"
        if not uvicorn_exec.exists():
            progress.stop()
            console.print("[bold red]Virtual environment not found. Please install dependencies first.[/bold red]")
            raise typer.Exit(1)
            
        try:
            if os.name == "nt":
                cmd = (
                    f"Start-Process powershell -ArgumentList '-NoExit','-Command',"
                    f"\"Set-Location '{BRAIN_DIR}'; & '{uvicorn_exec}' main:app --host 0.0.0.0 --port 8000 --reload\""
                )
                subprocess.Popen(["powershell", "-Command", cmd], shell=False)
            else:
                subprocess.Popen(
                    [str(uvicorn_exec), "main:app", "--port", "8000", "--reload"],
                    cwd=BRAIN_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            # Wait a moment for Brain to initialize
            time.sleep(2)
            progress.update(task_brain, completed=True, description="[green]Brain is alive.[/green]")
        except Exception as e:
            progress.stop()
            console.print(f"[bold red]Failed to launch Intelligence Brain: {e}[/bold red]")
            raise typer.Exit(1)
            
    console.print("\n[bold green]✅ System online. The Aqueitas Engine is now omnipresent.[/bold green]")


@app.command()
def logs(limit: int = typer.Option(10, help="Number of logs to fetch")):
    """View the most recent ingested commit logs"""
    console.print(f"\n[bold cyan]=== RECENT ENGINEERING LOGS ===[/bold cyan]\n")
    
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[cyan]Fetching logs from Sovereign Vault..."),
        transient=True,
    ) as progress:
        progress.add_task("fetch", total=None)
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"http://127.0.0.1:8000/logs?limit={limit}")
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as e:
            progress.stop()
            console.print("[bold red]Failed to connect to Intelligence Brain. Is it running?[/bold red]")
            raise typer.Exit(1)
        except httpx.HTTPStatusError as e:
            progress.stop()
            console.print(f"[bold red]Brain returned an error: {e.response.status_code}[/bold red]")
            raise typer.Exit(1)

    if not data:
        console.print("[yellow]No logs found in the Vault.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Timestamp", style="dim", width=20)
    table.add_column("Project", style="bold cyan")
    table.add_column("Summary")

    for log in data:
        # Created_at example format: 2026-06-19T10:45:00
        timestamp = log.get("created_at", "Unknown")[:19].replace("T", " ")
        project = log.get("project_name", "Unknown")
        content = log.get("log_content", "")
        # Get the first line or a summary of the content
        first_line = content.split("\n")[0][:80] + "..." if content else "No content"
        table.add_row(timestamp, project, first_line)
    
    console.print(table)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Natural-language question"), 
    limit: int = typer.Option(5, help="Max sources to return")
):
    """Query your technical memory"""
    with Progress(
        SpinnerColumn(spinner_name="earth"),
        TextColumn("[cyan]Querying Sovereign Vault for context..."),
        transient=True,
    ) as progress:
        progress.add_task("query", total=None)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    "http://127.0.0.1:8000/query",
                    json={"query": query, "limit": limit}
                )
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as e:
            progress.stop()
            console.print("[bold red]Failed to connect to Intelligence Brain. Is it running?[/bold red]")
            raise typer.Exit(1)
        except httpx.HTTPStatusError as e:
            progress.stop()
            console.print(f"[bold red]Brain returned an error: {e.response.status_code}[/bold red]")
            raise typer.Exit(1)

    answer = data.get("answer", "No answer generated.")
    sources = data.get("sources", [])
    
    console.print(f"\n[bold cyan]=== AQUEITAS INTELLIGENCE RETRIEVAL ===[/bold cyan]\n")
    
    console.print(Panel(answer, title="[bold blue]ANSWER[/bold blue]", border_style="blue"))
    
    console.print(f"\n[bold yellow]SOURCES[/bold yellow]")
    if not sources:
        console.print("  [dim]No historical logs matched this query.[/dim]")
    else:
        for idx, src in enumerate(sources, 1):
            project_name = src.get("project_name", "Unknown")
            log_id = src.get("log_id", "Unknown")
            console.print(f"  [bold]{idx}.[/bold] [cyan]{project_name}[/cyan] [dim](Log ID: {log_id})[/dim]")
    
    console.print("\n")


@app.command()
def status():
    """Quick health check"""
    doctor()

@app.command()
def doctor():
    """Deep diagnostics — keys, files, connectivity"""
    console.print("\n[bold cyan]=== Aqueitas Diagnostics ===[/bold cyan]\n")
    
    env_root = ROOT_DIR / ".env"
    env_brain = BRAIN_DIR / ".env"
    console.print(f"Root .env exists:  {'[green]Yes[/green]' if env_root.exists() else '[red]No[/red]'}")
    console.print(f"Brain .env exists: {'[green]Yes[/green]' if env_brain.exists() else '[red]No[/red]'}")
    
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get("http://127.0.0.1:8000/docs")
            status_text = "[green]Online[/green]" if r.status_code == 200 else f"[yellow]Code {r.status_code}[/yellow]"
    except httpx.RequestError:
        status_text = "[red]Offline[/red] (Is the Brain running?)"
        
    console.print(f"Brain API:         {status_text}\n")

@app.command()
def replay():
    """Re-ingest commits queued while the Brain was offline"""
    queue_file = ROOT_DIR / "sensor" / "queue.jsonl"
    if not queue_file.exists():
        console.print("[green]No offline commit queue found.[/green]")
        return

    entries = []
    malformed = []
    for line_no, line in enumerate(queue_file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            console.print(f"[yellow]Skipping malformed queue entry on line {line_no}: {exc}[/yellow]")
            malformed.append(line)
            continue
        replay_payload = dict(payload)
        replay_payload.pop("queued_at", None)
        entries.append((replay_payload, line))

    if not entries and not malformed:
        console.print("[green]Offline queue is empty.[/green]")
        queue_file.unlink()
        return

    remaining = []
    replayed_count = 0
    with httpx.Client(timeout=30.0) as client:
        for payload, original_line in entries:
            try:
                response = client.post("http://127.0.0.1:8000/log", json=payload)
                response.raise_for_status()
                replayed_count += 1
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                console.print(f"[red]Replay failed for {payload.get('project_name', 'unknown project')}: {exc}[/red]")
                remaining.append(original_line)

    remaining.extend(malformed)
    if remaining:
        queue_file.write_text(
            "\n".join(remaining) + "\n",
            encoding="utf-8",
        )
        console.print(f"[yellow]Replayed {replayed_count} entries; {len(remaining)} remain queued.[/yellow]")
        raise typer.Exit(1)

    queue_file.unlink()
    console.print(f"[green]Replayed {replayed_count} queued commits.[/green]")

@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) server over stdio for IDE integration"""
    try:
        from cli.mcp_server import start_mcp
        start_mcp()
    except ImportError as e:
        with open("mcp_error.txt", "w") as f:
            f.write(f"ImportError: {e}\n")
        console.stderr = True
        console.print(f"[bold red]Failed to load MCP server: {e}[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
