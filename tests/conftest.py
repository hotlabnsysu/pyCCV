# -*- coding: utf-8 -*-
"""Shared pytest fixtures for pyCCV tests."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture
def pyccv_caplog(caplog):
    """Yield `caplog` with its handler attached to the `pyCCV` logger.

    The project logger has ``propagate=False`` so pytest's built-in caplog
    (which relies on propagation to the root logger) would see no records
    otherwise. This fixture wires the handler in for the duration of the test
    and tears it down afterwards.
    """
    pyccv = logging.getLogger("pyCCV")
    pyccv.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger="pyCCV")
    try:
        yield caplog
    finally:
        pyccv.removeHandler(caplog.handler)
