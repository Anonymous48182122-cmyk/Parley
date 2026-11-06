"""
Every agent is defined in two places (agents/prompts.py and the frontend), plus a portrait and a colour. Adding
a dozen more is exactly when one of those gets forgotten, so this test names what is missing.
"""

import re
from pathlib import Path

from agents import prompts

ROOT = Path(__file__).resolve().parent
FRONT = ROOT / "frontend"


def _read(rel):
    return (FRONT / rel).read_text(encoding="utf-8")


def _frontend_meta():
    text = _read("src/agentMeta.js")
    meta = {}
    for m in re.finditer(r'^\s{2}([a-z_]+): \{ name: "([^"]+)", monogram: "[^"]+", role: "[^"]+", kind: "([a-z]+)"', text, re.M):
        meta[m.group(1)] = {"name": m.group(2), "kind": m.group(3)}
    return meta


def test_every_agent_is_defined_in_every_backend_table():
    for key in prompts.AGENTS:
        assert key in prompts.AGENT_DISPLAY_NAMES, f"{key}: no display name"
        assert key in prompts.AGENT_KIND, f"{key}: no kind"
        assert key in prompts.SYSTEM_PROMPTS, f"{key}: no system prompt"
        assert key in prompts.STAGE1_OUTPUT_SPEC, f"{key}: no first pass sections"
        assert prompts.STAGE1_OUTPUT_SPEC[key][-1] == "Verdict", f"{key}: sections must end with Verdict"
        assert key in prompts.FRAMEWORK_TESTS, f"{key}: no framework tests"


def test_the_frontend_knows_the_same_agents_with_the_same_names_and_kinds():
    meta = _frontend_meta()
    meta.pop("cio", None)  # the CIO is not a committee member; the page keeps its look beside the others
    order = re.search(r"AGENT_ORDER = \[(.*?)\];", _read("src/agentMeta.js"), re.S).group(1)
    ordered = [k for k in re.findall(r'"([a-z_]+)"', order) if k != "cio"]
    assert set(prompts.AGENTS) == set(meta), f"backend and frontend differ: {set(prompts.AGENTS) ^ set(meta)}"
    assert set(prompts.AGENTS) == set(ordered), f"AGENT_ORDER differs: {set(prompts.AGENTS) ^ set(ordered)}"
    for key in prompts.AGENTS:
        assert meta[key]["name"] == prompts.AGENT_DISPLAY_NAMES[key], f"{key}: name differs"
        assert meta[key]["kind"] == prompts.AGENT_KIND[key], f"{key}: kind differs"


def test_every_agent_has_a_colour_a_bio_and_real_people_have_a_portrait():
    css = _read("src/theme.css")
    bios = _read("src/agentBios.js")
    for key, kind in prompts.AGENT_KIND.items():
        assert f"--agent-{key}:" in css, f"{key}: no --agent-{key} colour in theme.css"
        assert re.search(rf"^\s{{2}}{key}:", bios, re.M), f"{key}: no bio in agentBios.js"
        if kind in ("investor", "legend"):
            assert (FRONT / "public" / "avatars" / f"{key}.webp").exists(), f"{key}: no portrait in public/avatars"
