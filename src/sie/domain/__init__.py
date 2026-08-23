"""Framework-agnostic domain layer: models, errors, and ports (interfaces).

This package must never import from ``infrastructure``, ``api`` -- or any
third-party library. Dependencies point inward only.
"""
