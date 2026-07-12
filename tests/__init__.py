"""Repository-local test helper package.

Importing from this package (`from tests.helpers.... import ...`) is safe even
when a third-party top-level ``tests`` package is installed in the environment:
because ``tests`` is a real package rooted at the repository root (see
``tests/__init__.py``) and the repository root is prepended to ``sys.path`` by
pytest, the repository-local ``tests`` always wins over any installed
``site-packages/tests``.
"""
