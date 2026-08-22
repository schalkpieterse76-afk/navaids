"""Thales ATM TCP/IP framing protocol client for MCS CVOR systems.

Frame format:
    STX (0x02) | length (2 bytes, big-endian) | JSON payload | ETX (0x03)
"""

import json
import socket
import struct
import logging

STX = 0x02
ETX = 0x03
DEFAULT_TIMEOUT = 5.0

logger = logging.getLogger(__name__)


def _frame(payload: dict) -> bytes:
    """Encode a dict as a Thales ATM framed TCP message."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    length = struct.pack(">H", len(body))
    return bytes([STX]) + length + body + bytes([ETX])


def _unframe(data: bytes) -> dict:
    """Decode a Thales ATM framed TCP response to a dict."""
    if not data or data[0] != STX:
        raise ValueError("Missing STX byte in response")
    if data[-1] != ETX:
        raise ValueError("Missing ETX byte in response")
    length = struct.unpack(">H", data[1:3])[0]
    body = data[3: 3 + length]
    return json.loads(body.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from sock, handling partial reads."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed before all bytes were received")
        buf += chunk
    return buf


def send_command(ip: str, port: int, command: dict, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Open a TCP connection, send a framed command and return the decoded response.

    Args:
        ip: Target CVOR system IP address.
        port: Target TCP port (default 4000 for Thales ATM).
        command: Dict to send as the JSON payload.
        timeout: Socket timeout in seconds.

    Returns:
        Decoded response dict.

    Raises:
        ConnectionError: On TCP or framing errors.
    """
    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.sendall(_frame(command))
            # Read framed response: STX (1) + length (2) = 3 header bytes
            header = _recv_exact(sock, 3)
            if header[0] != STX:
                raise ValueError("Missing STX byte in response header")
            body_len = struct.unpack(">H", header[1:3])[0]
            # Read body + ETX
            body = _recv_exact(sock, body_len + 1)
            if body[-1] != ETX:
                raise ValueError("Missing ETX byte at end of response")
            return json.loads(body[:-1].decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("TCP command to %s:%d failed: %s", ip, port, exc)
        raise ConnectionError(str(exc)) from exc


def ping(ip: str, port: int, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Return True if the CVOR system responds to a PING command."""
    try:
        response = send_command(ip, port, {"cmd": "PING"}, timeout=timeout)
        return response.get("status") == "OK"
    except ConnectionError:
        return False


def poll_status(ip: str, port: int, system_id: int) -> dict:
    """Poll the current operational status of a CVOR system."""
    return send_command(ip, port, {"cmd": "GET_STATUS", "system_id": system_id})


def set_frequency(ip: str, port: int, system_id: int, frequency: float) -> dict:
    return send_command(ip, port, {"cmd": "SET_FREQ", "system_id": system_id, "value": frequency})


def set_power(ip: str, port: int, system_id: int, level: str) -> dict:
    return send_command(ip, port, {"cmd": "SET_POWER", "system_id": system_id, "value": level})


def set_mode(ip: str, port: int, system_id: int, mode: str) -> dict:
    return send_command(ip, port, {"cmd": "SET_MODE", "system_id": system_id, "value": mode})


def set_ident(ip: str, port: int, system_id: int, ident: str) -> dict:
    return send_command(ip, port, {"cmd": "SET_IDENT", "system_id": system_id, "value": ident})


def reboot(ip: str, port: int, system_id: int) -> dict:
    return send_command(ip, port, {"cmd": "REBOOT", "system_id": system_id})


def emergency_stop(ip: str, port: int, system_id: int) -> dict:
    return send_command(ip, port, {"cmd": "ESTOP", "system_id": system_id})


def get_alarms(ip: str, port: int, system_id: int) -> dict:
    return send_command(ip, port, {"cmd": "GET_ALARMS", "system_id": system_id})
