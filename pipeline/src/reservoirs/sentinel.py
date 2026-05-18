"""Sentinel-2 and Sentinel-1 live area extraction stages."""

from __future__ import annotations


def extract_s2_recent(*_args, **_kwargs):
    """Extract current reservoir area from Sentinel-2."""

    raise NotImplementedError("Sentinel-2 extraction requires Earth Engine implementation")


def extract_s1_recent(*_args, **_kwargs):
    """Extract current reservoir area from Sentinel-1 SAR fallback."""

    raise NotImplementedError("Sentinel-1 extraction requires Earth Engine implementation")

