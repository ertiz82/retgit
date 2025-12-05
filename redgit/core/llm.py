import json
import os
import shutil
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import List, Dict, Optional

# API client imports (optional)
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Load providers from JSON
PROVIDERS_FILE = Path(__file__).parent / "llm_providers.json"


def load_providers() -> Dict[str, dict]:
    """Load LLM providers from JSON file"""
    if PROVIDERS_FILE.exists():
        with open(PROVIDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("providers", {})
    return {}


def check_provider_available(name: str, config: dict) -> bool:
    """Check if a provider is available"""
    provider_type = config.get("type")

    if provider_type == "cli":
        cmd = config.get("cmd")
        return shutil.which(cmd) is not None

    elif provider_type == "api":
        env_key = config.get("env_key")

        # Ollama: check if command exists
        if name == "ollama":
            return shutil.which("ollama") is not None

        # OpenAI-based: check package and env var
        if name in ("openai", "openrouter"):
            return HAS_OPENAI and (env_key is None or os.environ.get(env_key))

        # Anthropic: check package and env var
        if name == "claude-api":
            return HAS_ANTHROPIC and (env_key is None or os.environ.get(env_key))

    return False


def get_available_providers() -> Dict[str, dict]:
    """Return providers that are currently available"""
    providers = load_providers()
    available = {}
    for name, config in providers.items():
        if check_provider_available(name, config):
            available[name] = config
    return available


def get_all_providers() -> Dict[str, dict]:
    """Return all provider definitions"""
    return load_providers()


def install_provider(provider: str) -> bool:
    """Install a provider (CLI-based only)"""
    providers = load_providers()
    if provider not in providers:
        return False

    config = providers[provider]
    install_cmd = config.get("install")

    if not install_cmd:
        return False

    try:
        subprocess.run(install_cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


class LLMClient:
    """
    LLM client supporting both CLI and API-based providers.

    Providers are loaded from llm_providers.json

    Config example (.redgit/config.yaml):
        llm:
          provider: openai
          model: gpt-4o
          timeout: 120
          api_key: sk-...  # optional, can use env var
    """

    def __init__(self, config: dict):
        self.timeout = config.get("timeout", 120)
        self.provider_name = config.get("provider", "auto")
        self.model = config.get("model")
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url")

        # Load providers
        self.providers = load_providers()

        # Auto-detect provider if needed
        if self.provider_name == "auto":
            self.provider_name = self._detect_provider()

        if self.provider_name not in self.providers:
            raise ValueError(f"Unknown LLM provider: {self.provider_name}")

        self.provider_config = self.providers[self.provider_name]

        # Set default model if not specified
        if not self.model:
            self.model = self.provider_config.get("default_model")

        # Validate provider is available
        if not check_provider_available(self.provider_name, self.provider_config):
            raise FileNotFoundError(
                f"Provider '{self.provider_name}' is not available.\n"
                f"Install: {self.provider_config.get('install')}"
            )

        self.provider = self.provider_name  # For backwards compatibility

    def _detect_provider(self) -> str:
        """Auto-detect available provider"""
        # Priority order
        priority = ["claude-code", "qwen-code", "ollama", "openai", "claude-api", "openrouter"]

        for name in priority:
            if name in self.providers and check_provider_available(name, self.providers[name]):
                return name

        raise FileNotFoundError(
            "No LLM provider found. Install one of:\n"
            "  - claude-code: npm install -g @anthropic-ai/claude-code\n"
            "  - openai: pip install openai && export OPENAI_API_KEY=...\n"
            "  - ollama: curl -fsSL https://ollama.com/install.sh | sh"
        )

    def generate_groups(self, prompt: str) -> List[Dict]:
        """Send prompt to LLM and get commit groups"""
        provider_type = self.provider_config.get("type")

        if provider_type == "cli":
            return self._run_cli(prompt)
        elif provider_type == "api":
            return self._run_api(prompt)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    def _run_cli(self, prompt: str) -> List[Dict]:
        """Run CLI-based LLM"""
        if self.provider_name == "claude-code":
            return self._run_claude_cli(prompt)
        elif self.provider_name == "qwen-code":
            return self._run_qwen_cli(prompt)
        else:
            raise ValueError(f"Unknown CLI provider: {self.provider_name}")

    def _run_claude_cli(self, prompt: str) -> List[Dict]:
        """Run Claude Code CLI"""
        env = os.environ.copy()
        env["NO_COLOR"] = "1"

        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=env
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI error: {result.stderr or result.stdout}")

        return self._parse_yaml(result.stdout)

    def _run_qwen_cli(self, prompt: str) -> List[Dict]:
        """Run Qwen Code CLI"""
        env = os.environ.copy()
        env["NO_COLOR"] = "1"

        # Use -p/--prompt for non-interactive mode with prompt as argument
        result = subprocess.run(
            ["qwen", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=env
        )

        if result.returncode != 0:
            raise RuntimeError(f"Qwen CLI error: {result.stderr or result.stdout}")

        return self._parse_yaml(result.stdout)

    def _run_api(self, prompt: str) -> List[Dict]:
        """Run API-based LLM"""
        if self.provider_name == "openai":
            return self._run_openai(prompt)
        elif self.provider_name == "claude-api":
            return self._run_anthropic(prompt)
        elif self.provider_name == "ollama":
            return self._run_ollama(prompt)
        elif self.provider_name == "openrouter":
            return self._run_openrouter(prompt)
        else:
            raise ValueError(f"Unknown API provider: {self.provider_name}")

    def _run_openai(self, prompt: str) -> List[Dict]:
        """Run OpenAI API"""
        if not HAS_OPENAI:
            raise ImportError("openai package not installed. Run: pip install openai")

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes code changes and groups them into logical commits. Always respond with valid YAML."},
                {"role": "user", "content": prompt}
            ],
            timeout=self.timeout
        )

        return self._parse_yaml(response.choices[0].message.content)

    def _run_anthropic(self, prompt: str) -> List[Dict]:
        """Run Anthropic Claude API"""
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return self._parse_yaml(response.content[0].text)

    def _run_ollama(self, prompt: str) -> List[Dict]:
        """Run Ollama local API"""
        if not HAS_REQUESTS:
            raise ImportError("requests package not installed. Run: pip install requests")

        import requests
        base_url = self.base_url or self.provider_config.get("base_url", "http://localhost:11434")

        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            },
            timeout=self.timeout
        )
        response.raise_for_status()

        return self._parse_yaml(response.json()["response"])

    def _run_openrouter(self, prompt: str) -> List[Dict]:
        """Run OpenRouter API (OpenAI-compatible)"""
        if not HAS_OPENAI:
            raise ImportError("openai package not installed. Run: pip install openai")

        api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        base_url = self.base_url or self.provider_config.get("base_url", "https://openrouter.ai/api/v1")

        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes code changes and groups them into logical commits. Always respond with valid YAML."},
                {"role": "user", "content": prompt}
            ],
            timeout=self.timeout
        )

        return self._parse_yaml(response.choices[0].message.content)

    def _parse_yaml(self, output: str) -> List[Dict]:
        """Parse YAML block from LLM output"""
        # Find ```yaml ... ``` block
        start = output.find("```yaml")
        if start == -1:
            start = output.find("```yml")

        if start != -1:
            end = output.find("```", start + 7)
            yaml_text = output[start + 7:end].strip() if end != -1 else output[start + 7:].strip()
        else:
            # Try parsing entire output as YAML
            yaml_text = output.strip()

        try:
            data = yaml.safe_load(yaml_text)
            if isinstance(data, dict):
                return data.get("groups", [])
            return []
        except Exception as e:
            raise ValueError(f"YAML parse error: {e}\n\nOutput:\n{output[:500]}")