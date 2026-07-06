"""
iptables command executor — runs iptables commands safely via subprocess.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
from typing import Any

from security_agent.firewall.exceptions import OperationValidationError

logger = logging.getLogger("firewall.executor")

IPTABLES_BIN = "/sbin/iptables"
CHAIN_NAME = "AI_SECURITY_AGENT"


def validate_ip(ip_str: str) -> str:
    try:
        return str(ipaddress.ip_address(ip_str))
    except ValueError as e:
        raise OperationValidationError(f"Invalid IP: {ip_str}") from e


class IptablesExecutor:
    """Executes iptables commands safely via subprocess with argument lists."""

    def __init__(self, iptables_bin: str = IPTABLES_BIN) -> None:
        self._bin = iptables_bin

    async def run(self, args: list[str], timeout: int = 10) -> tuple[int, str]:
        cmd = [self._bin] + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, (stderr or b"").decode(
                "utf-8", errors="replace"
            )
        except TimeoutError:
            return -1, f"Timed out after {timeout}s"
        except FileNotFoundError:
            return -2, f"Not found: {self._bin}"
        except Exception as e:
            return -3, str(e)

    async def create_chain(self) -> bool:
        code, err = await self.run(["-N", CHAIN_NAME])
        if code == 1 and "already exists" in err:
            return True
        if code != 0:
            logger.error("Chain creation failed", extra={"error": err})
            return False
        logger.info("Created chain %s", CHAIN_NAME)
        return True

    async def ensure_chain_referenced(self) -> bool:
        check = await self.run(["-C", "INPUT", "-j", CHAIN_NAME])
        if check[0] == 0:
            return True
        code, err = await self.run(
            [
                "-I",
                "INPUT",
                "-j",
                CHAIN_NAME,
                "-m",
                "comment",
                "--comment",
                "AI Security Agent",
            ]
        )
        if code != 0:
            logger.error("Chain reference failed", extra={"error": err})
            return False
        return True

    async def add_rule(self, ip_str: str, comment: str = "") -> bool:
        ip = validate_ip(ip_str)
        args = ["-A", CHAIN_NAME, "-s", ip, "-j", "DROP"]
        if comment:
            args += ["-m", "comment", "--comment", comment[:256]]
        code, err = await self.run(args)
        if code == 1 and "already exists" in err:
            return True
        if code != 0:
            logger.error("Add rule failed", extra={"ip": ip, "error": err})
            return False
        return True

    async def remove_rule(self, ip_str: str) -> bool:
        ip = validate_ip(ip_str)
        code, err = await self.run(["-D", CHAIN_NAME, "-s", ip, "-j", "DROP"])
        if code == 1 and "does matching rule" in err:
            return True
        if code != 0:
            logger.error("Remove rule failed", extra={"ip": ip, "error": err})
            return False
        return True

    async def rule_exists(self, ip_str: str) -> bool:
        ip = validate_ip(ip_str)
        code, _ = await self.run(["-C", CHAIN_NAME, "-s", ip, "-j", "DROP"])
        return code == 0

    async def list_rules(self) -> list[dict[str, Any]]:
        code, output = await self.run(["-S", CHAIN_NAME])
        if code != 0:
            return []
        rules: list[dict[str, Any]] = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            rule: dict[str, Any] = {"raw": line}
            for i, part in enumerate(parts):
                if part == "-s" and i + 1 < len(parts):
                    rule["source"] = parts[i + 1]
                if part == "--comment" and i + 1 < len(parts):
                    rule["comment"] = parts[i + 1].strip('"')
            rules.append(rule)
        return rules

    async def flush_chain(self) -> bool:
        code, err = await self.run(["-F", CHAIN_NAME])
        if code != 0:
            logger.error("Flush failed", extra={"error": err})
            return False
        return True

    async def delete_chain(self) -> bool:
        code, err = await self.run(["-X", CHAIN_NAME])
        if code != 0:
            logger.error("Delete chain failed", extra={"error": err})
            return False
        return True
