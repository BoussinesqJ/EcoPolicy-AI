# -*- coding: utf-8 -*-
"""
region_loader.py - Province/City region source loader.

Loads YAML configuration files from the regions/ directory.
Supports alias resolution and parent-province chaining.
"""

import os
import sys
import glob
import yaml
from typing import Optional


def _load_all_regions(regions_dir: str) -> dict:
    """Load all region YAML files from a directory.

    Returns:
        dict: {canonical_name: region_config_dict}
    """
    regions = {}
    if not os.path.isdir(regions_dir):
        return regions

    pattern = os.path.join(regions_dir, "*.yaml")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and "name" in data:
                canonical = data["name"]
                data["_filepath"] = filepath
                regions[canonical] = data
        except Exception as e:
            print(f"[WARN] Failed to load {filepath}: {e}", file=sys.stderr)

    return regions


def _build_alias_map(regions: dict) -> dict:
    """Build alias -> canonical_name mapping.

    Returns:
        dict: {"hubei": "湖北省", "湖北": "湖北省", "鄂": "湖北省", ...}
    """
    alias_map = {}
    for canonical, config in regions.items():
        # Map canonical name to itself
        alias_map[canonical] = canonical
        # Map all aliases
        for alias in config.get("aliases", []):
            alias_map[str(alias).strip()] = canonical
    return alias_map


def resolve_region_name(name: str, alias_map: dict) -> Optional[str]:
    """Resolve a user-provided region name to its canonical form.

    Args:
        name: User input (e.g., "湖北", "湖北省", "鄂", "hubei")
        alias_map: The alias map from _build_alias_map()

    Returns:
        Canonical name or None if not found
    """
    # Direct match
    if name in alias_map:
        return alias_map[name]

    # Case-insensitive match for pinyin aliases
    name_lower = name.lower()
    for alias, canonical in alias_map.items():
        if alias.lower() == name_lower:
            return canonical

    # Partial match (e.g., user types "恩施" matches "恩施州")
    for alias, canonical in alias_map.items():
        if name in alias or alias in name:
            return canonical

    return None


def get_sources_for_region(
    region_name: str,
    regions_dir: str,
    include_national: bool = True,
    national_sources: list = None,
) -> dict:
    """Get all sources for a region, including parent province chain.

    Args:
        region_name: Region canonical name (e.g., "恩施州")
        regions_dir: Path to regions/ directory
        include_national: Whether to include national-level sources
        national_sources: List of national source configs from main config

    Returns:
        dict with keys:
            - region_chain: list of region names in the chain (e.g., ["恩施州", "湖北省"])
            - sources: list of source configs (merged national + regional)
            - region: the region config dict for the requested region
    """
    regions = _load_all_regions(regions_dir)
    alias_map = _build_alias_map(regions)

    # Resolve the region name
    canonical = resolve_region_name(region_name, alias_map)
    if not canonical:
        return {
            "region_chain": [],
            "sources": list(national_sources or []),
            "region": None,
            "error": f"Region '{region_name}' not found. Use --list-regions to see available regions.",
        }

    # Build the chain: region + all parent provinces
    chain = [canonical]
    current = regions.get(canonical, {})
    parent = current.get("parent_province")
    while parent:
        parent_canonical = resolve_region_name(parent, alias_map)
        if parent_canonical and parent_canonical not in chain:
            chain.append(parent_canonical)
            parent = regions.get(parent_canonical, {}).get("parent_province")
        else:
            break

    # Collect all sources from the chain
    region_sources = []
    for name in chain:
        region_config = regions.get(name, {})
        for src in region_config.get("sources", []):
            # Tag with region name for tracking
            src_copy = dict(src)
            src_copy["_region"] = name
            region_sources.append(src_copy)

    # Merge national + regional
    all_sources = []
    if include_national and national_sources:
        for src in national_sources:
            src_copy = dict(src)
            src_copy.setdefault("_region", "national")
            all_sources.append(src_copy)
    all_sources.extend(region_sources)

    return {
        "region_chain": chain,
        "sources": all_sources,
        "region": regions.get(canonical),
        "error": None,
    }


def list_all_regions(regions_dir: str) -> list:
    """List all available regions with metadata.

    Returns:
        list of dicts with name, aliases, parent_province, source_count
    """
    regions = _load_all_regions(regions_dir)
    result = []
    for canonical, config in sorted(regions.items()):
        result.append({
            "name": canonical,
            "aliases": config.get("aliases", []),
            "parent_province": config.get("parent_province"),
            "source_count": len(config.get("sources", [])),
        })
    return result
