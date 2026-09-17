"""
Cookie parsing utilities for Netscape / curl / yt-dlp format cookies.txt files.
"""
import os
import re
from typing import List, Dict, Any, Optional


def parse_cookie_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a Netscape / curl format cookies.txt file (standard format used by yt-dlp).

    Format:
    domain <tab> include_subdomains <tab> path <tab> secure <tab> expires <tab> name <tab> value
    Lines starting with '#HttpOnly_' indicate httpOnly=True.

    Returns:
        List of cookie dictionaries compatible with Playwright's `context.add_cookies()`.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Cookie file not found: {file_path}")

    cookies: List[Dict[str, Any]] = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            # Skip empty lines or pure comment lines (except #HttpOnly_)
            if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
                continue

            http_only = False
            if line.startswith("#HttpOnly_"):
                http_only = True
                line = line[len("#HttpOnly_"):]

            # Standard delimiter is Tab, but fallback to multiple spaces if edited by text editors
            parts = line.split("\t")
            if len(parts) < 7:
                parts = re.split(r"\s+", line, maxsplit=6)

            if len(parts) >= 7:
                domain = parts[0].strip()
                # include_subdomains = parts[1].strip()
                path = parts[2].strip() or "/"
                secure = parts[3].strip().upper() == "TRUE"
                
                try:
                    expires_val = float(parts[4].strip())
                except (ValueError, TypeError):
                    expires_val = -1

                name = parts[5].strip()
                # Value can be empty or the rest of the string
                value = parts[6].strip() if len(parts) > 6 else ""

                cookie_dict: Dict[str, Any] = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "secure": secure,
                    "httpOnly": http_only,
                }

                # Only include valid positive expiration
                if expires_val > 0:
                    cookie_dict["expires"] = expires_val

                cookies.append(cookie_dict)

    return cookies
