#!/usr/bin/env python3
"""
JUnit Agent — entry point.

Usage:
    python main.py                      # uses config.yaml in this directory
    python main.py --config my.yaml     # custom config
    python main.py --project /path/java # override project root from CLI
"""

import argparse
import sys
from pathlib import Path

import yaml

from agent.orchestrator import Orchestrator


def load_config(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.is_file():
        sys.exit(f"Config file not found: {cfg_path}")
    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    # Validate the essentials
    key = config.get("provider", {}).get("api_key", "")
    if not key or key == "PUT_YOUR_GROQ_API_KEY_HERE":
        sys.exit(
            "No API key set. Edit config.yaml and put your key in "
            "provider.api_key (get one at https://console.groq.com/keys)."
        )
    return config


def main():
    parser = argparse.ArgumentParser(description="Autonomous JUnit test generator agent")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--project", default=None, help="Override project root")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.project:
        config.setdefault("project", {})["root"] = args.project

    print("\n" + "=" * 56)
    print("  JUnit Agent")
    print(f"  Model    {config['provider']['model']}")
    print(f"  Endpoint {config['provider']['base_url']}")
    print(f"  Project  {config['project']['root']}")
    print("=" * 56 + "\n")

    Orchestrator(config).run()


if __name__ == "__main__":
    main()
