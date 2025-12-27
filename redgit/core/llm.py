import json
import os
import shutil
import subprocess
import yaml
from pathlib import Path
from typing import List, Dict

from .constants import LLM_REQUEST_TIMEOUT, MAX_ERROR_OUTPUT_LENGTH

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
    import requests  # noqa: F401
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
        self.timeout = config.get("timeout", LLM_REQUEST_TIMEOUT)
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

    def generate_groups(self, prompt: str, return_raw: bool = False):
        """Send prompt to LLM and get commit groups

        Args:
            prompt: The prompt to send to the LLM
            return_raw: If True, return tuple of (groups, raw_response)

        Returns:
            List[Dict] or tuple(List[Dict], str) if return_raw=True
        """
        provider_type = self.provider_config.get("type")

        if provider_type == "cli":
            groups, raw = self._run_cli(prompt, return_raw=True)
        elif provider_type == "api":
            groups, raw = self._run_api(prompt, return_raw=True)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

        if return_raw:
            return groups, raw
        return groups

    def chat(self, prompt: str) -> str:
        """Send prompt to LLM and get raw text response"""
        provider_type = self.provider_config.get("type")

        if provider_type == "cli":
            return self._chat_cli(prompt)
        elif provider_type == "api":
            return self._chat_api(prompt)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    def generate_task_filtered_groups(self, prompt: str, return_raw: bool = False) -> dict:
        """
        Generate task-filtered commit groups.

        Sends prompt to LLM and parses response into three categories:
        - related_groups: Files related to the parent task (subtasks)
        - other_task_matches: Files matching other active tasks
        - unmatched_files: Files not matching any task

        Args:
            prompt: The task-filtered prompt
            return_raw: If True, return tuple of (result, raw_response)

        Returns:
            Dict with keys: related_groups, other_task_matches, unmatched_files
        """
        # Get raw response from LLM
        raw_output = self.chat(prompt)

        # Parse the response
        result = self._parse_task_filtered_response(raw_output)

        if return_raw:
            return result, raw_output
        return result

    def _parse_task_filtered_response(self, output: str) -> dict:
        """
        Parse JSON response for task-filtered mode.

        Expected format:
        {
            "related_groups": [...],
            "other_task_matches": [...],
            "unmatched_files": [...]
        }
        """
        default = {
            "related_groups": [],
            "other_task_matches": [],
            "unmatched_files": []
        }

        # Try to find JSON in the output
        # First, try to find a JSON code block
        json_text = None
        for marker in ["```json", "```"]:
            start = output.find(marker)
            if start != -1:
                marker_len = len(marker)
                end = output.find("```", start + marker_len)
                if end != -1:
                    json_text = output[start + marker_len:end].strip()
                    break

        # If no code block, try to find raw JSON
        if json_text is None:
            # Look for JSON object
            start = output.find("{")
            end = output.rfind("}") + 1
            if start >= 0 and end > start:
                json_text = output[start:end]

        if not json_text:
            return default

        try:
            data = json.loads(json_text)

            # Validate and return with defaults for missing keys
            return {
                "related_groups": data.get("related_groups", []),
                "other_task_matches": data.get("other_task_matches", []),
                "unmatched_files": data.get("unmatched_files", [])
            }
        except json.JSONDecodeError:
            # Try YAML as fallback
            try:
                data = yaml.safe_load(json_text)
                if isinstance(data, dict):
                    return {
                        "related_groups": data.get("related_groups", []),
                        "other_task_matches": data.get("other_task_matches", []),
                        "unmatched_files": data.get("unmatched_files", [])
                    }
            except Exception:
                pass

            return default

    def _chat_cli(self, prompt: str) -> str:
        """Run CLI-based LLM for chat"""
        env = os.environ.copy()
        env["NO_COLOR"] = "1"

        if self.provider_name == "claude-code":
            cmd = ["claude", "-p", prompt]
        elif self.provider_name == "qwen-code":
            cmd = ["qwen", prompt]
        else:
            raise ValueError(f"Unknown CLI provider: {self.provider_name}")

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            raise RuntimeError(f"LLM CLI error: {result.stderr}")

        return result.stdout.strip()

    def _chat_api(self, prompt: str) -> str:
        """Run API-based LLM for chat"""
        if self.provider_name == "openai":
            return self._chat_openai(prompt)
        elif self.provider_name == "anthropic":
            return self._chat_anthropic(prompt)
        elif self.provider_name == "ollama":
            return self._chat_ollama(prompt)
        elif self.provider_name == "openrouter":
            return self._chat_openrouter(prompt)
        else:
            raise ValueError(f"Unknown API provider: {self.provider_name}")

    def _chat_openai(self, prompt: str) -> str:
        """Chat with OpenAI API"""
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content

    def _chat_anthropic(self, prompt: str) -> str:
        """Chat with Anthropic API"""
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _chat_ollama(self, prompt: str) -> str:
        """Chat with Ollama API"""
        import requests
        base_url = self.provider_config.get("base_url", "http://localhost:11434")
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False}
        )
        return response.json().get("response", "")

    def _chat_openrouter(self, prompt: str) -> str:
        """Chat with OpenRouter API"""
        import requests
        api_key = os.environ.get("OPENROUTER_API_KEY")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        )
        return response.json()["choices"][0]["message"]["content"]

    def _run_cli(self, prompt: str, return_raw: bool = False):
        """Run CLI-based LLM"""
        if self.provider_name == "claude-code":
            return self._run_claude_cli(prompt, return_raw)
        elif self.provider_name == "qwen-code":
            return self._run_qwen_cli(prompt, return_raw)
        else:
            raise ValueError(f"Unknown CLI provider: {self.provider_name}")

    def _run_claude_cli(self, prompt: str, return_raw: bool = False):
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

        raw_output = result.stdout
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _run_qwen_cli(self, prompt: str, return_raw: bool = False):
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

        raw_output = result.stdout
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _run_api(self, prompt: str, return_raw: bool = False):
        """Run API-based LLM"""
        if self.provider_name == "openai":
            return self._run_openai(prompt, return_raw)
        elif self.provider_name == "claude-api":
            return self._run_anthropic(prompt, return_raw)
        elif self.provider_name == "ollama":
            return self._run_ollama(prompt, return_raw)
        elif self.provider_name == "openrouter":
            return self._run_openrouter(prompt, return_raw)
        else:
            raise ValueError(f"Unknown API provider: {self.provider_name}")

    def _run_openai(self, prompt: str, return_raw: bool = False):
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

        raw_output = response.choices[0].message.content
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _run_anthropic(self, prompt: str, return_raw: bool = False):
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

        raw_output = response.content[0].text
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _run_ollama(self, prompt: str, return_raw: bool = False):
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

        raw_output = response.json()["response"]
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _run_openrouter(self, prompt: str, return_raw: bool = False):
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

        raw_output = response.choices[0].message.content
        groups = self._parse_yaml(raw_output)

        if return_raw:
            return groups, raw_output
        return groups

    def _parse_yaml(self, output: str) -> List[Dict]:
        """Parse YAML or JSON block from LLM output"""
        import json

        # Find code block - check for yaml, yml, or json
        yaml_text = None
        for marker in ["```yaml", "```yml", "```json"]:
            start = output.find(marker)
            if start != -1:
                marker_len = len(marker)
                end = output.find("```", start + marker_len)
                yaml_text = output[start + marker_len:end].strip() if end != -1 else output[start + marker_len:].strip()
                break

        if yaml_text is None:
            # Try parsing entire output as YAML
            yaml_text = output.strip()

        # Clean up common LLM output issues
        yaml_text = self._clean_yaml_output(yaml_text)

        try:
            # Try JSON first (handles both JSON and YAML for simple cases)
            try:
                data = json.loads(yaml_text)
            except json.JSONDecodeError:
                data = yaml.safe_load(yaml_text)

            # Handle both list and dict responses
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("groups", [])
            return []
        except Exception as e:
            raise ValueError(f"YAML parse error: {e}\n\nOutput:\n{output[:500]}")

    def _clean_yaml_output(self, text: str) -> str:
        """Clean common LLM output issues in YAML"""
        import re

        # Remove leading "yaml" or "yml" word (without ```)
        # Handles cases like "yaml\ngroups:" or "yamlyaml\ngroups:"
        text = re.sub(r'^(yaml|yml)+\s*\n?', '', text, flags=re.IGNORECASE)

        # Remove duplicate "groups" at start (handles "groupsyaml\ngroups:")
        text = re.sub(r'^groups(yaml|yml)?\s*\n', '', text, flags=re.IGNORECASE)

        # Find and extract valid YAML starting with "groups:"
        groups_match = re.search(r'^(groups:\s*\n)', text, re.MULTILINE)
        if groups_match:
            # Get everything from "groups:" onwards
            start_pos = groups_match.start()
            text = text[start_pos:]

        return text.strip()