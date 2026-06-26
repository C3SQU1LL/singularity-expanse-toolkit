#!/usr/bin/env python3
"""Import procedural .solar/.json star systems into The Singularity Expanse Notion databases.

Designed to run in GitHub Actions so the user does not need Python installed locally.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

NOTION_VERSION = "2022-06-28"
API_BASE = "https://api.notion.com/v1"

DBS = {
    "stars": os.getenv("STARS_DB_ID", "32ebaf348bba80ed8348cd81e5ef88fb"),
    "planets": os.getenv("PLANETS_DB_ID", "32ebaf348bba8076982afb7b42262ba4"),
    "moons": os.getenv("MOONS_DB_ID", "32fbaf348bba80a399c0f1fae5d193bc"),
}


def clean_db_id(value: str) -> str:
    return value.split("?")[0].replace("-", "").strip()


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "yes", "true", "y"}


def load_system(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    text = p.read_text(encoding="utf-8", errors="replace").strip()
    # Some copied exports may contain text before/after JSON. Trim to first { and last }.
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def title_text(system: Dict[str, Any]) -> str:
    return str(system.get("name") or "Unnamed System")


def spectral_class(temp: Optional[float]) -> str:
    if temp is None:
        return "Unknown"
    if temp >= 30000: return "O"
    if temp >= 10000: return "B"
    if temp >= 7500: return "A"
    if temp >= 6000: return "F"
    if temp >= 5200: return "G"
    if temp >= 3700: return "K"
    return "M"


def star_type(temp: Optional[float], wd: bool) -> str:
    if wd:
        return "White Dwarf"
    c = spectral_class(temp)
    return {
        "O": "Blue Main Sequence Star",
        "B": "Blue-White Main Sequence Star",
        "A": "White Main Sequence Star",
        "F": "Yellow-White Main Sequence Star",
        "G": "Yellow Main Sequence Star",
        "K": "Orange Main Sequence Star",
        "M": "Red Dwarf Star",
    }.get(c, "Main Sequence Star")


def classify_body(body: Dict[str, Any], is_moon: bool = False) -> str:
    gas = float(body.get("gas") or 0)
    ice = float(body.get("ice") or 0)
    rock = float(body.get("rock") or 0)
    metal = float(body.get("metal") or 0)
    mass = float(body.get("mass") or 0)
    if gas >= 0.5:
        return "Gas Giant" if mass >= 50 else "Ice Giant"
    if ice >= 0.45 and rock >= 0.2:
        return "Icy Moon" if is_moon else "Ice-Rich World"
    if metal >= 0.45:
        return "Metal-Rich World"
    if mass >= 2 and rock >= 0.45:
        return "Super-Earth"
    if rock >= 0.55:
        return "Rocky Moon" if is_moon else "Terrestrial Planet"
    return "Minor Moon" if is_moon else "Minor Planet"


def life_sign(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return "Unknown"
    return {0: "No Life", 1: "Microbial Life", 2: "Complex Life", 3: "Intelligent Life"}.get(n, "Unknown")


def tectonic_status(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return "Unknown"
    return {0: "Geologically Dead", 1: "Mildly Active", 2: "Active", 3: "Highly Active"}.get(n, "Unknown")


def fluid_state(value: Any) -> str:
    s = str(value)
    if s == "-1": return "No Stable Surface Liquid"
    if s == "0": return "Surface Liquid Present"
    if s == "1": return "Liquid Present"
    return "Unknown"


def tidal_lock(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return "Unknown"
    return {0: "Not Tidally Locked", 1: "Tidally Locked", 2: "Orbital Synchronisation"}.get(n, "Unknown")


def as_number(value: Any) -> Optional[float]:
    if value is None or value == "": return None
    try:
        f = float(value)
        if math.isfinite(f): return f
    except Exception:
        return None
    return None


def notion_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


class NotionClient:
    def __init__(self, token: str):
        self.token = token
        self.headers = notion_headers(token)
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        for attempt in range(5):
            resp = requests.request(method, url, headers=self.headers, timeout=30, **kwargs)
            if resp.status_code == 429:
                delay = int(resp.headers.get("Retry-After", "1"))
                time.sleep(delay + 0.5)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Notion API error {resp.status_code}: {resp.text}")
            return resp.json()
        raise RuntimeError("Notion API rate limit did not clear after retries")

    def schema(self, db_id: str) -> Dict[str, Any]:
        db_id = clean_db_id(db_id)
        if db_id not in self.schemas:
            data = self.request("GET", f"{API_BASE}/databases/{db_id}")
            self.schemas[db_id] = data["properties"]
        return self.schemas[db_id]

    def find_by_name(self, db_id: str, name: str) -> Optional[str]:
        schema = self.schema(db_id)
        title_prop = next((k for k, v in schema.items() if v.get("type") == "title"), "Name")
        payload = {
            "filter": {"property": title_prop, "title": {"equals": name}},
            "page_size": 1,
        }
        data = self.request("POST", f"{API_BASE}/databases/{clean_db_id(db_id)}/query", json=payload)
        results = data.get("results", [])
        return results[0]["id"] if results else None

    def build_prop(self, schema_prop: Dict[str, Any], value: Any) -> Optional[Dict[str, Any]]:
        typ = schema_prop.get("type")
        if value is None:
            return None
        if typ == "title":
            return {"title": [{"text": {"content": str(value)}}]}
        if typ == "rich_text":
            return {"rich_text": [{"text": {"content": str(value)}}]}
        if typ == "number":
            num = as_number(value)
            return {"number": num} if num is not None else None
        if typ == "checkbox":
            return {"checkbox": bool(value)}
        if typ == "select":
            if value == "": return None
            return {"select": {"name": str(value)}}
        if typ == "multi_select":
            if isinstance(value, list):
                return {"multi_select": [{"name": str(v)} for v in value if str(v).strip()]}
            return {"multi_select": [{"name": str(value)}]} if str(value).strip() else None
        if typ == "url":
            return {"url": str(value)} if str(value).startswith(("http://", "https://")) else None
        if typ == "relation":
            if isinstance(value, list):
                return {"relation": [{"id": v} for v in value]}
            return {"relation": [{"id": value}]} if value else None
        # Skip formula, rollup, created_time, last_edited_time, etc.
        return None

    def create_page(self, db_id: str, values: Dict[str, Any]) -> str:
        schema = self.schema(db_id)
        props: Dict[str, Any] = {}
        for name, value in values.items():
            if name not in schema:
                continue
            built = self.build_prop(schema[name], value)
            if built is not None:
                props[name] = built
        payload = {"parent": {"database_id": clean_db_id(db_id)}, "properties": props}
        data = self.request("POST", f"{API_BASE}/pages", json=payload)
        return data["id"]


def star_values(system: Dict[str, Any]) -> Dict[str, Any]:
    temp = as_number(system.get("temp"))
    luma = as_number(system.get("luma"))
    mass_est = None
    if luma and luma > 0:
        mass_est = luma ** (1 / 3.5)
    name = title_text(system)
    return {
        "Name": name,
        "Luminosity (Solar)": luma,
        "Solar Temperature": temp,
        "System Age (bn years)": (as_number(system.get("age")) or 0) / 1000 if as_number(system.get("age")) else None,
        "Mass (Solar)": mass_est,
        "Spectral Class": spectral_class(temp),
        "Star Type": star_type(temp, bool(system.get("WD"))),
        "System Type": "Single Star System",
        "Survey Status": "Generated",
        "Description": f"Procedurally imported star system containing {len(system.get('planets', []))} planets.",
        "Stellar Description": f"{star_type(temp, bool(system.get('WD')))} with luminosity {luma:.3g} L☉ and temperature {temp:.0f} K." if luma and temp else "Procedurally imported star.",
    }


def planet_values(p: Dict[str, Any], star_id: str, system: Dict[str, Any]) -> Dict[str, Any]:
    name = str(p.get("name") or f"Planet {p.get('index', '')}")
    atm = str(p.get("atmobasegas") or "none")
    distance = as_number(p.get("distanceFromParent"))
    return {
        "Name": name,
        "Parent Star": star_id,
        "Planet Distance from Star (AU)": distance,
        "Distance from Star": distance,
        "Raw Mass": as_number(p.get("mass")),
        "Mass": as_number(p.get("mass")),
        "Star Luminosity (Solar)": as_number(system.get("luma")),
        "System Age (bn years)": (as_number(system.get("age")) or 0) / 1000 if as_number(system.get("age")) else None,
        "Day Length": f"{as_number(p.get('dayCycle')):.3f} Earth days" if as_number(p.get("dayCycle")) is not None else None,
        "Atmospheric Composition": "None" if atm == "none" else atm.title(),
        "Atmosphere Density Factor": as_number(p.get("atmothickness")),
        "Atmospheric Pressure": as_number(p.get("atmothickness")),
        "Fluid State": fluid_state(p.get("liquid")),
        "Life Sign": life_sign(p.get("life")),
        "Tectonic Status": tectonic_status(p.get("geoactive")),
        "Classification": classify_body(p, False),
        "Orbital Synchronisation": tidal_lock(p.get("tidalLock")),
        "Dominant Crustal Composition": dominant_composition(p),
        "Planetary Description": planet_description(p),
        "Description": planet_description(p),
    }


def moon_values(m: Dict[str, Any], planet_id: str) -> Dict[str, Any]:
    name = str(m.get("name") or f"Moon {m.get('index', '')}")
    atm = str(m.get("atmobasegas") or "none")
    return {
        "Name": name,
        "Parent Planet": planet_id,
        "Calculated Orbital Distance": as_number(m.get("distanceFromParent")),
        "Orbit Period": f"{as_number(m.get('dayCycle')):.3f} Earth days" if as_number(m.get("dayCycle")) is not None else None,
        "Rotational Period": f"{as_number(m.get('dayCycle')):.3f} Earth days" if as_number(m.get("dayCycle")) is not None else None,
        "Atmosphere": "None" if atm == "none" else atm.title(),
        "Life Sign": life_sign(m.get("life")),
        "Satellite Class": classify_body(m, True),
        "Tidal Locking Prediction": tidal_lock(m.get("tidalLock")),
        "Lunar Description": moon_description(m),
    }


def dominant_composition(b: Dict[str, Any]) -> str:
    parts = {
        "Metal": float(b.get("metal") or 0),
        "Rock": float(b.get("rock") or 0),
        "Ice": float(b.get("ice") or 0),
        "Gas": float(b.get("gas") or 0),
    }
    return max(parts, key=parts.get)


def planet_description(p: Dict[str, Any]) -> str:
    return (
        f"Procedurally imported {classify_body(p)}. "
        f"Composition: {float(p.get('rock') or 0):.0%} rock, {float(p.get('ice') or 0):.0%} ice, "
        f"{float(p.get('gas') or 0):.0%} gas, {float(p.get('metal') or 0):.0%} metal. "
        f"Life status: {life_sign(p.get('life'))}."
    )


def moon_description(m: Dict[str, Any]) -> str:
    return (
        f"Procedurally imported {classify_body(m, True)}. "
        f"Composition: {float(m.get('rock') or 0):.0%} rock, {float(m.get('ice') or 0):.0%} ice, "
        f"{float(m.get('metal') or 0):.0%} metal. Life status: {life_sign(m.get('life'))}."
    )


def import_system(system: Dict[str, Any], dry_run: bool) -> None:
    star_name = title_text(system)
    planets = system.get("planets", []) or []
    moons = [m for p in planets for m in (p.get("moons", []) or [])]
    print("=" * 72)
    print("The Singularity Expanse Notion Importer")
    print("=" * 72)
    print(f"System: {star_name}")
    print(f"Planets: {len(planets)}")
    print(f"Moons: {len(moons)}")
    print(f"Mode: {'DRY RUN - no Notion changes' if dry_run else 'IMPORT - writing to Notion'}")
    print("=" * 72)

    if dry_run:
        print("\nStar preview:")
        print(json.dumps(star_values(system), indent=2, ensure_ascii=False))
        print("\nPlanets:")
        for p in planets:
            print(f"- {p.get('name')} ({classify_body(p)}) | moons: {len(p.get('moons', []) or [])}")
        print("\nDry run complete. Run again with dry_run=false to import.")
        return

    token = os.getenv("NOTION_TOKEN")
    if not token:
        raise RuntimeError("Missing GitHub secret NOTION_TOKEN.")

    client = NotionClient(token)
    star_db, planet_db, moon_db = DBS["stars"], DBS["planets"], DBS["moons"]

    existing_star = client.find_by_name(star_db, star_name)
    if existing_star:
        star_id = existing_star
        print(f"Star already exists, using existing page: {star_name}")
    else:
        star_id = client.create_page(star_db, star_values(system))
        print(f"Created star: {star_name}")

    planet_ids: Dict[int, str] = {}
    for p in planets:
        pname = str(p.get("name") or f"Planet {p.get('index', '')}")
        existing = client.find_by_name(planet_db, pname)
        if existing:
            pid = existing
            print(f"Planet already exists, using existing page: {pname}")
        else:
            pid = client.create_page(planet_db, planet_values(p, star_id, system))
            print(f"Created planet: {pname}")
        planet_ids[int(p.get("index", len(planet_ids)))] = pid

        for m in p.get("moons", []) or []:
            mname = str(m.get("name") or f"Moon {m.get('index', '')}")
            existing_moon = client.find_by_name(moon_db, mname)
            if existing_moon:
                print(f"Moon already exists, skipped: {mname}")
                continue
            client.create_page(moon_db, moon_values(m, pid))
            print(f"Created moon: {mname}")

    print("\nImport complete.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("solar_file", help="Path to .solar/.json/.txt file")
    parser.add_argument("--dry-run", default="true", help="true or false")
    args = parser.parse_args()
    try:
        system = load_system(args.solar_file)
        import_system(system, dry_run=parse_bool(args.dry_run))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
