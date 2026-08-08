"""Crow Workbench application layer."""

from pathlib import Path

from fastapi import FastAPI


def create_app(data_root: Path | None = None) -> FastAPI:
    from .shell import create_app as create_shell_app

    return create_shell_app(data_root)


__all__ = ["create_app"]
