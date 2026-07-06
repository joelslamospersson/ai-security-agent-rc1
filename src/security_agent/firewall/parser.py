"""iptables output parser — parses rule listings into structured data."""

from __future__ import annotations

from typing import Any


def parse_iptables_save(output: str) -> dict[str, list[dict[str, Any]]]:
    """Parse `iptables-save` output into structured chain data."""
    chains: dict[str, list[dict[str, Any]]] = {}
    current_chain: str = ""

    for line in output.strip().split("\n"):
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        if line.startswith("*"):
            continue
        if line.startswith(":"):
            parts = line.split()
            if parts:
                current_chain = parts[0][1:]
                chains[current_chain] = []
            continue
        if line.startswith("COMMIT"):
            continue
        if line.startswith("-A"):
            rule = parse_rule_line(line)
            if rule:
                chain_name = rule.pop("chain", current_chain)
                if chain_name not in chains:
                    chains[chain_name] = []
                chains[chain_name].append(rule)

    return chains


def parse_rule_line(line: str) -> dict[str, Any]:
    """Parse a single iptables rule line into structured data."""
    rule: dict[str, Any] = {"raw": line}
    parts = line.split()
    for i, part in enumerate(parts):
        if part == "-A" and i + 1 < len(parts):
            rule["chain"] = parts[i + 1]
        if part == "-s" and i + 1 < len(parts):
            rule["source"] = parts[i + 1]
        if part == "-d" and i + 1 < len(parts):
            rule["dest"] = parts[i + 1]
        if part == "-j" and i + 1 < len(parts):
            rule["target"] = parts[i + 1]
        if part == "-p" and i + 1 < len(parts):
            rule["protocol"] = parts[i + 1]
        if part == "--dport" and i + 1 < len(parts):
            rule["dport"] = parts[i + 1]
        if part == "--comment" and i + 1 < len(parts):
            rule["comment"] = parts[i + 1].strip('"')
        if part == "-m":
            pass
    return rule


def extract_ips_from_rules(rules: list[dict[str, Any]]) -> set[str]:
    """Extract source IPs from a list of parsed rules."""
    ips: set[str] = set()
    for rule in rules:
        src = rule.get("source", "")
        if src and not src.startswith("0.0.0.0"):
            ips.add(src)
    return ips


def count_rules_for_chain(rules_output: str, chain: str = "AI_SECURITY_AGENT") -> int:
    """Count rules in a specific chain from iptables -S output."""
    count = 0
    for line in rules_output.strip().split("\n"):
        if line.strip().startswith(f"-A {chain}"):
            count += 1
    return count
