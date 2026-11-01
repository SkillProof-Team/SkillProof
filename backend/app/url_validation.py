"""Validate URL authorities before trusting urllib's deliberately permissive parser."""

from urllib.parse import urlsplit


def authority_hostname(authority: str) -> str:
    """Accept a host or host:port, not userinfo, paths, queries or malformed ports.

    urlsplit alone is not validation: it will parse ``user@host/path`` and only
    raises for an invalid port when the ``port`` property is accessed.
    IPv6 literals must retain brackets, as required in an HTTP Host field.
    """
    if (
        not authority
        or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in authority)
        or any(c in authority for c in "@/\\?#")
        or authority.endswith(":")
    ):
        raise ValueError("Invalid URL authority")
    parsed = urlsplit("//" + authority)
    port = parsed.port  # Access validates the numeric syntax and upper bound.
    if not parsed.hostname or parsed.path or parsed.query or parsed.fragment or port == 0:
        raise ValueError("Invalid URL authority")
    return parsed.hostname


def https_url(value: str):
    """Return a parsed absolute HTTPS URL without credentials or ambiguous syntax."""
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Invalid HTTPS URL")
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise ValueError("HTTPS required")
    authority_hostname(parsed.netloc)
    return parsed
