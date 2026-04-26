"""Headscale firewall/network policy ownership."""

import logging
import subprocess

logger = logging.getLogger(__name__)


def configure_tailscale_firewall():
    """Ensure firewall rules allow GhostHub, Headscale, and relay traffic."""
    logger.info("Configuring firewall rules for Tailscale, DERP, and relay traffic...")
    try:
        existing_rules = subprocess.run(
            ["sudo", "iptables", "-L", "INPUT", "-n"],
            capture_output=True,
            text=True,
            check=False,
        )
        rules_text = existing_rules.stdout

        if "tailscale0" not in rules_text or "dpt:5000" not in rules_text:
            subprocess.run(
                ["sudo", "iptables", "-I", "INPUT", "1", "-i", "tailscale0", "-p", "tcp", "--dport", "5000", "-j", "ACCEPT"],
                check=False,
            )
        if "100.64.0.0/10" not in rules_text:
            subprocess.run(
                ["sudo", "iptables", "-I", "INPUT", "1", "-s", "100.64.0.0/10", "-p", "tcp", "--dport", "5000", "-j", "ACCEPT"],
                check=False,
            )

        if "dpt:8080" not in rules_text:
            subprocess.run(
                ["sudo", "iptables", "-I", "INPUT", "1", "-p", "tcp", "--dport", "8080", "-j", "ACCEPT"],
                check=False,
            )

        if "dpt:3478" not in rules_text:
            subprocess.run(
                ["sudo", "iptables", "-I", "INPUT", "1", "-p", "udp", "--dport", "3478", "-j", "ACCEPT"],
                check=False,
            )

        if "dpt:41641" not in rules_text:
            subprocess.run(
                ["sudo", "iptables", "-I", "INPUT", "1", "-p", "udp", "--dport", "41641", "-j", "ACCEPT"],
                check=False,
            )

        existing_forward = subprocess.run(
            ["sudo", "iptables", "-L", "FORWARD", "-n"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "tailscale0" not in existing_forward.stdout:
            subprocess.run(["sudo", "iptables", "-I", "FORWARD", "1", "-i", "tailscale0", "-j", "ACCEPT"], check=False)
            subprocess.run(["sudo", "iptables", "-I", "FORWARD", "1", "-o", "tailscale0", "-j", "ACCEPT"], check=False)

        subprocess.run(["sudo", "netfilter-persistent", "save"], check=False)
        subprocess.run(["sudo", "iptables-save"], capture_output=True, check=False)
        logger.info("Firewall rules configured and saved for Tailscale, DERP, and relay traffic")
        return True
    except Exception as err:
        logger.warning("Failed to configure firewall rules: %s", err)
        return False
