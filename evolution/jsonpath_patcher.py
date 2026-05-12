# evolution/jsonpath_patcher.py
# AUTOLOOP V2 — Structured-config JSON-path patcher
# Pattern source: Meir770ar/agentic-video-maker scripts/patch-plan.cjs (MIT, REPOEVAL REFERENCE_ONLY)
# Spec: docs/EVOLVER-JSONPATH.md
# Issue: TBD

"""
Apply LLM-generated structured patches to JSON/YAML config files.

PARALLELS evolver.py BUT FOR JSON/YAML, NOT MARKDOWN:
  evolver.py emits   EvolutionEntry(section, content)   → merge into SKILL.md
  this module emits  JsonPathEntry(field, new_value)    → mutate config dict

CORE PRIMITIVES (lifted from patch-plan.cjs, normalized for Python):
  - parse_path("scenes[3].text_position")  → ["scenes", 3, "text_position"]
  - path_exists(obj, parts)                → parent-existence check before set
  - set_path(obj, parts, value)            → mutate dict in place
  - coerce(v)                              → "3.14" → 3.14, "true" → True, etc.
  - AUTO_CREATE_ROOTS                      → per-target via WhitelistConfig.auto_create_roots

EXIT-CODE SEMANTICS (matches patch-plan.cjs CLI contract):
  apply_patches() returns PatchResult with:
    - total_applied:  > 0 → success (CLI exit 0)
    - total_applied: == 0 → no-op (CLI exit 1)
    - exceptions    → fatal (CLI exit 2)

HONESTY (per Honesty V3):
  - VERIFIED: round-trip unit tests against the exact patch-plan.cjs test fixtures
              (see evolution/tests/test_jsonpath_patcher.py)
  - INFERRED: behavioral equivalence with JS version for edge cases (Levenshtein, NaN, etc)
  - UNTESTED: integration with evolver.py / signal_detector.py (separate PR)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from .jsonpath_schema import JsonPathEntry, WhitelistConfig
from .schema import EntryAction


# ── Path parser ───────────────────────────────────────────────────────────────
# Mirrors patch-plan.cjs parsePath():
#   "scenes[3].text_position" → ["scenes", 3, "text_position"]
#   "audio_mix.music_volume"  → ["audio_mix", "music_volume"]
#   "tags[0][2]"              → ["tags", 0, 2]
# Returns None for unparseable input.

_TOKEN_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)((?:\[\d+\])*)$")
_INDEX_RE = re.compile(r"\[(\d+)\]")


def parse_path(dotted: str) -> Optional[list[Union[str, int]]]:
    """Parse a dotted+indexed path. Returns None on bad input."""
    if not dotted or not isinstance(dotted, str):
        return None
    parts: list[Union[str, int]] = []
    for tok in dotted.split("."):
        m = _TOKEN_RE.match(tok)
        if not m:
            return None
        parts.append(m.group(1))
        idx_block = m.group(2) or ""
        for idx_match in _INDEX_RE.finditer(idx_block):
            parts.append(int(idx_match.group(1)))
    return parts


# ── Existence / mutation helpers ──────────────────────────────────────────────

_Container = Union[dict, list]


def path_exists(obj: Any, parts: list[Union[str, int]]) -> bool:
    """
    Parent-existence check: returns True iff parts[:-1] navigates a container.

    This intentionally checks the PARENT of the leaf (so the leaf can be set
    even if it doesn't exist yet), mirroring patch-plan.cjs pathExists.
    """
    cur: Any = obj
    for k in parts[:-1]:
        if cur is None:
            return False
        if isinstance(cur, dict):
            if k not in cur:
                return False
            cur = cur[k]
        elif isinstance(cur, list):
            if not isinstance(k, int):
                return False
            if k < 0 or k >= len(cur):
                return False
            cur = cur[k]
        else:
            return False
    return isinstance(cur, (dict, list))


def set_path(obj: _Container, parts: list[Union[str, int]], value: Any) -> None:
    """In-place set. Assumes path_exists() returned True. Raises if not."""
    cur: Any = obj
    for k in parts[:-1]:
        cur = cur[k]
    leaf = parts[-1]
    if isinstance(cur, list):
        if not isinstance(leaf, int):
            raise TypeError(f"cannot use non-int key {leaf!r} on list")
        # Allow append-at-end for lists (one slot past)
        if leaf == len(cur):
            cur.append(value)
        else:
            cur[leaf] = value
    else:
        cur[leaf] = value


def ensure_path_parent(obj: dict, parts: list[Union[str, int]], auto_create_roots: set[str]) -> bool:
    """
    Mirrors patch-plan.cjs ensurePathParent + AUTO_CREATE_ROOTS:
    if the root (parts[0]) is whitelisted for auto-create and absent, materialize as {}.
    Returns True iff parent now exists.
    """
    if len(parts) < 2:
        return True
    root = parts[0]
    if not isinstance(root, str):
        return False
    if root not in auto_create_roots:
        return False
    if root not in obj or not isinstance(obj[root], dict):
        obj[root] = {}
    # Re-check after materialization
    return path_exists(obj, parts)


# ── Value coercion ────────────────────────────────────────────────────────────
# patch-plan.cjs's coerce() turns LLM string outputs into proper types.
# We're stricter than JS because Python's type system is too.

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d*\.\d+$")


def coerce(v: Any) -> Any:
    """Coerce a string value to bool/int/float when it matches. Pass-through otherwise."""
    if not isinstance(v, str):
        return v
    if v == "true":
        return True
    if v == "false":
        return False
    if _INT_RE.match(v):
        return int(v)
    if _FLOAT_RE.match(v):
        return float(v)
    return v


# ── Result model ──────────────────────────────────────────────────────────────

@dataclass
class AppliedPatch:
    field: str
    new_value: Any
    reason: Optional[str] = None
    scene_index: Optional[int] = None  # populated when patching scenes[N].* (back-compat with video-maker semantics)


@dataclass
class SkippedPatch:
    field: str
    reason: str


@dataclass
class PatchResult:
    """Mirrors patch-plan.cjs's stdout JSON contract."""
    applied: list[AppliedPatch] = field(default_factory=list)
    skipped: list[SkippedPatch] = field(default_factory=list)
    scenes_to_regen: list[int] = field(default_factory=list)  # back-compat; harmless for non-scene targets

    @property
    def total_applied(self) -> int:
        return len(self.applied)

    @property
    def total_skipped(self) -> int:
        return len(self.skipped)

    @property
    def cli_exit_code(self) -> int:
        """Mirrors patch-plan.cjs exit semantics: 0=applied, 1=none."""
        return 0 if self.total_applied > 0 else 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": [
                {"field": a.field, "new_value": a.new_value, "reason": a.reason}
                for a in self.applied
            ],
            "skipped": [{"field": s.field, "reason": s.reason} for s in self.skipped],
            "scenes_to_regen": self.scenes_to_regen,
            "total_applied": self.total_applied,
            "total_skipped": self.total_skipped,
        }


# ── Main patcher ──────────────────────────────────────────────────────────────

class JsonPathPatcher:
    """
    Apply a list of JsonPathEntry mutations to a config dict, respecting a WhitelistConfig.

    USAGE:
        config = json.loads(Path("sentinel-thresholds.json").read_text())
        wl = WhitelistConfig(
            target="sentinel-thresholds",
            allowed_paths={r"^thresholds\\.[a-z_]+$": dict(type="number", min=0, max=1000)},
            auto_create_roots={"thresholds"},
        )
        patcher = JsonPathPatcher(whitelist=wl)
        entries = [JsonPathEntry(skill_name="sentinel", target="sentinel-thresholds",
                                 field="thresholds.alert_threshold", new_value="50")]
        result = patcher.apply(config, entries)
        # result.total_applied == 1
        # config["thresholds"]["alert_threshold"] == 50  (coerced from "50")

    Mark scenes as 'pending' (back-compat with video-maker upstream): if any patched
    field starts with "scenes[N].", the patcher records N in result.scenes_to_regen.
    The caller decides what to do with that signal.
    """

    def __init__(self, whitelist: WhitelistConfig):
        self.whitelist = whitelist

    def apply(self, config: dict, entries: list[JsonPathEntry]) -> PatchResult:
        result = PatchResult()
        scenes_seen: set[int] = set()

        for entry in entries:
            if entry.action == EntryAction.SKIP:
                result.skipped.append(SkippedPatch(field=entry.field, reason=entry.skip_reason or "explicit skip"))
                continue

            parts = parse_path(entry.field)
            if parts is None:
                result.skipped.append(SkippedPatch(field=entry.field, reason="unparseable path"))
                continue

            # Coerce value early so whitelist type-check sees the final type
            new_value = coerce(entry.new_value)

            # Whitelist gate
            ok, why = self.whitelist.validate_value(entry.field, new_value)
            if not ok:
                result.skipped.append(SkippedPatch(field=entry.field, reason=why))
                continue

            # Parent existence (with auto-create for whitelisted roots)
            if not path_exists(config, parts):
                if not ensure_path_parent(config, parts, self.whitelist.auto_create_roots):
                    result.skipped.append(SkippedPatch(field=entry.field, reason="path not in config"))
                    continue

            # Apply
            try:
                set_path(config, parts, new_value)
            except (TypeError, IndexError, KeyError) as exc:
                result.skipped.append(SkippedPatch(field=entry.field, reason=f"set failed: {exc}"))
                continue

            result.applied.append(AppliedPatch(field=entry.field, new_value=new_value))

            # Video-maker back-compat: mark scenes[N].* for regen
            if parts[0] == "scenes" and len(parts) >= 2 and isinstance(parts[1], int):
                scenes_seen.add(parts[1])

        # Convert array indices back to 1-based scene .i values when the schema uses them
        # (matches patch-plan.cjs lines 121-124 — scenes have an `i` field that's 1-based).
        scenes_list = config.get("scenes")
        if isinstance(scenes_list, list):
            for arr_idx in scenes_seen:
                if 0 <= arr_idx < len(scenes_list):
                    scene = scenes_list[arr_idx]
                    if isinstance(scene, dict):
                        scene_i = scene.get("i")
                        if scene_i is not None:
                            result.scenes_to_regen.append(scene_i)
                        # Mark as pending + clear cached asset_path (matches upstream behavior)
                        scene["status"] = "pending"
                        scene.pop("asset_path", None)

        return result


# ── CLI entry point (matches patch-plan.cjs invocation contract) ──────────────

def main(argv: Optional[list[str]] = None) -> int:
    """
    CLI: python -m evolution.jsonpath_patcher <plan.json> <critique.json> <output_plan.json>

    Reads plan.json (the config to mutate) and critique.json (LLM output with
    `issues[].plan_patch{field, new_value}` per the agentic-video-maker schema),
    applies whitelisted patches, writes output_plan.json.

    No whitelist registered by CLI → uses a permissive default (everything allowed,
    auto_create_roots={"text_style","audio_mix"}) for drop-in patch-plan.cjs compatibility.
    Production callers should always construct an explicit WhitelistConfig.
    """
    import sys
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 3:
        print("Usage: python -m evolution.jsonpath_patcher <plan.json> <critique.json> <output_plan.json>",
              file=sys.stderr)
        return 2

    plan_path, critique_path, out_path = argv

    try:
        plan = json.loads(Path(plan_path).read_text())
        critique = json.loads(Path(critique_path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read input: {exc}", file=sys.stderr)
        return 2

    # Permissive default whitelist for drop-in patch-plan.cjs compat.
    default_wl = WhitelistConfig(
        target="default",
        allowed_paths={
            r"^scenes\[\d+\]\.duration_sec$":            dict(type="number"),
            r"^scenes\[\d+\]\.text_on_screen$":          dict(type="string"),
            r"^scenes\[\d+\]\.text_position$":           dict(type="enum",
                                                              values=["bottom-center","top-center","lower-third","center"]),
            r"^scenes\[\d+\]\.ken_burns$":               dict(type="enum",
                                                              values=["zoom_in_center","zoom_out_center","pan_left","pan_right","pan_up"]),
            r"^scenes\[\d+\]\.image_prompt$":            dict(type="string"),
            r"^text_style\.font_size_multiplier$":       dict(type="number", min=0.7, max=2.0),
            r"^text_style\.position$":                   dict(type="enum",
                                                              values=["bottom-center","top-center","lower-third","center"]),
            r"^audio_mix\.narration_volume$":            dict(type="number"),
            r"^audio_mix\.music_volume$":                dict(type="number"),
            r"^music_mood$":                             dict(type="string"),
            r"^title$":                                  dict(type="string"),
            r"^subtitle$":                               dict(type="string"),
            r"^outro$":                                  dict(type="string"),
        },
        auto_create_roots={"text_style", "audio_mix"},
    )

    entries: list[JsonPathEntry] = []
    for issue in critique.get("issues", []):
        patch_blob = issue.get("plan_patch")
        if not isinstance(patch_blob, dict):
            continue
        f_ = patch_blob.get("field")
        v_ = patch_blob.get("new_value")
        if not f_:
            continue
        entries.append(JsonPathEntry(
            skill_name="<cli>",
            target="default",
            field=f_,
            new_value=v_,
        ))

    patcher = JsonPathPatcher(whitelist=default_wl)
    result = patcher.apply(plan, entries)

    Path(out_path).write_text(json.dumps(plan, indent=2))
    print(json.dumps(result.to_dict(), indent=2))
    return result.cli_exit_code


if __name__ == "__main__":
    import sys
    sys.exit(main())
