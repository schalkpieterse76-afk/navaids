"""File parsers for MCS CVOR Remote Management System.

Supports:
  - .ini          standard Python ConfigParser format
  - config.sys    key=value lines (no sections)
  - .LDA          Thales ATM LDA binary/text export
"""

import configparser
import io
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# .ini parser
# ---------------------------------------------------------------------------

def parse_ini(content: str) -> dict:
    """Parse an .ini file string and return a nested dict {section: {key: value}}."""
    parser = configparser.ConfigParser()
    try:
        parser.read_string(content)
    except configparser.Error as exc:
        logger.error("INI parse error: %s", exc)
        return {}
    result = {}
    for section in parser.sections():
        result[section] = dict(parser[section])
    return result


# ---------------------------------------------------------------------------
# config.sys parser  (key=value, no section headers)
# ---------------------------------------------------------------------------

def parse_config_sys(content: str) -> dict:
    """Parse a config.sys style file (plain key=value pairs) into a flat dict."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip().upper()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# .LDA parser  (Thales ATM LDA export – simplified text representation)
# ---------------------------------------------------------------------------


def parse_lda(content: str) -> list:
    """Parse a Thales ATM .LDA text export into a list of record dicts.

    Each record has at minimum a ``record_type`` key followed by the
    field key/value pairs extracted from the line.

    Example LDA line::

        CVOR_PARAM | FREQ=116.300 | IDENT=WKF | POWER=HIGH | MODE=NORMAL

    Returns:
        List of dicts, one per non-comment line.
    """
    records = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        # Split on pipe to get record type and fields – no complex regex needed
        parts = line.split("|")
        record_type = parts[0].strip()
        # Validate record type: must be uppercase letters and underscores only
        if not record_type or not all(c.isalpha() or c == "_" for c in record_type):
            continue
        record = {"record_type": record_type}
        for part in parts[1:]:
            part = part.strip()
            if "=" not in part:
                continue
            eq_pos = part.index("=")
            key = part[:eq_pos].strip()
            value = part[eq_pos + 1:].strip()
            # Validate key: uppercase letters and underscores only
            if key and all(c.isalpha() or c == "_" for c in key):
                record[key] = value
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------

def parse_file(filename: str, content: str):
    """Detect file type by extension and return parsed data.

    Args:
        filename: Original filename (used to determine parser).
        content: File contents as a string.

    Returns:
        Parsed data (dict or list depending on file type).
    """
    lower = filename.lower()
    if lower.endswith(".ini"):
        return parse_ini(content)
    if lower.endswith(".lda"):
        return parse_lda(content)
    if lower in ("config.sys",) or lower.endswith("config.sys"):
        return parse_config_sys(content)
    # Fallback: try ini, then config.sys
    try:
        result = parse_ini(content)
        if result:
            return result
    except Exception:
        pass
    return parse_config_sys(content)
