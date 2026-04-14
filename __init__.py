"""Citric process engineering application package."""

__all__ = [
    "app",
    "main",
]


def main():
    """Lazy entry-point – imports web_app only when called."""
    from .web_app import main as _main  # noqa: delay import to avoid circular dependency
    return _main()


app = main