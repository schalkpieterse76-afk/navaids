"""OS-agnostic network subnet and gateway auto-detection for MCS."""

import socket
import logging

logger = logging.getLogger(__name__)


def _ipv4_interfaces():
    """Return a list of (iface_name, ip, netmask) tuples for all IPv4 interfaces."""
    results = []
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            ipv4 = addrs.get(netifaces.AF_INET, [])
            for entry in ipv4:
                ip = entry.get("addr", "")
                netmask = entry.get("netmask", "255.255.255.0")
                if ip and not ip.startswith("127."):
                    results.append((iface, ip, netmask))
    except ImportError:
        logger.warning("netifaces not available; falling back to hostname resolution")
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and not ip.startswith("127."):
                results.append(("eth0", ip, "255.255.255.0"))
        except OSError:
            pass
    return results


def _default_gateway():
    """Return the default IPv4 gateway as a string, or empty string."""
    try:
        import netifaces
        gateways = netifaces.gateways()
        default = gateways.get("default", {})
        ipv4_gw = default.get(netifaces.AF_INET)
        if ipv4_gw:
            return ipv4_gw[0]
    except ImportError:
        pass
    return ""


def _cidr_from_netmask(netmask: str) -> int:
    """Convert dotted-decimal netmask to CIDR prefix length."""
    try:
        parts = [int(p) for p in netmask.split(".")]
        return sum(bin(p).count("1") for p in parts)
    except (ValueError, AttributeError):
        return 24


def get_local_network_info() -> dict:
    """Return a dict with the local machine's primary network configuration.

    Returns:
        {
            "ip": str,
            "netmask": str,
            "gateway": str,
            "cidr": int,
            "subnet": str,   e.g. "192.168.1.0/24"
            "interfaces": [{"name": str, "ip": str, "netmask": str}, ...]
        }
    """
    interfaces = _ipv4_interfaces()
    gateway = _default_gateway()

    if interfaces:
        _, primary_ip, primary_netmask = interfaces[0]
    else:
        primary_ip = "0.0.0.0"
        primary_netmask = "255.255.255.0"

    cidr = _cidr_from_netmask(primary_netmask)
    # Calculate subnet base address
    try:
        ip_parts = [int(p) for p in primary_ip.split(".")]
        mask_parts = [int(p) for p in primary_netmask.split(".")]
        subnet_parts = [ip_parts[i] & mask_parts[i] for i in range(4)]
        subnet = ".".join(str(p) for p in subnet_parts) + f"/{cidr}"
    except (ValueError, IndexError):
        subnet = f"{primary_ip}/{cidr}"

    return {
        "ip": primary_ip,
        "netmask": primary_netmask,
        "gateway": gateway,
        "cidr": cidr,
        "subnet": subnet,
        "interfaces": [
            {"name": name, "ip": ip, "netmask": nm} for name, ip, nm in interfaces
        ],
    }
