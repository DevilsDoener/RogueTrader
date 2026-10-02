"""Response headers that need no per-request decision: CSP and Permissions-Policy.

Django 5.2 has no built-in Content-Security-Policy. The portal is fully
self-hosted -- no CDN, no web fonts, no third-party URLs, no inline scripts or
event handlers -- so the policy can be strict:

* ``script-src 'self'``: only the files under ``/static/`` run. An inline
  ``<script>`` (or an injected one) is refused by the browser; ``json_script``
  blocks (``type="application/json"``) are data, not executed, and stay fine.
* ``style-src 'self'`` plus ``style-src-attr 'unsafe-inline'``: stylesheets come
  from files; the sheet viewer positions its fields with per-element ``style=""``
  attributes (geometry), which is why attributes alone are allowed inline.
  JavaScript setting ``element.style...`` (CSSOM) is not affected by CSP.
* ``img-src 'self' data:``: the checkbox marks in ``sheet-viewer.css`` are
  ``data:`` SVGs.
* ``frame-ancestors 'none'`` mirrors ``X-Frame-Options: DENY``; ``base-uri
  'none'`` and ``object-src 'none'`` close the remaining injection routes.

An inline script added to a template later therefore breaks visibly, which is
intended: ``core/tests/test_security_headers.py`` fails on it first.
"""

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "style-src-attr 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
    )
)

PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class SecurityHeadersMiddleware:
    """Add the CSP and Permissions-Policy headers to every response.

    A view that sets either header itself keeps its own value. The middleware
    sits first in ``MIDDLEWARE`` so that responses WhiteNoise serves directly
    (static files) and redirects from ``SecurityMiddleware`` carry the headers
    too.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response
