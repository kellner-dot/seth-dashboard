#!/usr/bin/env python3
"""KaviBOT Gate 1: read-only UIA tree observation (Windows).

Dumps a single window's accessibility tree via pywinauto (UIA backend)
and emits NORMALIZED JSON to stdout. READ-ONLY by construction: this
script imports nothing that can act (no Invoke/SetValue/click/type),
touches no input APIs, and creates no persistent state.

Usage (on SETHS-PC):
    python a11y_dump.py --title "Notepad" [--process notepad.exe]
                        [--max-depth 12] [--max-nodes 2000]

Output: {"schema": "a11y-tree-1.0", "provenance": {...},
         "nodes": {...}, "root": "n0"}
Exit codes: 0 ok | 2 window not found | 3 inaccessible (e.g. elevated)
"""
import argparse
import hashlib
import json
import sys
import time
import uuid

SCHEMA_VERSION = "a11y-tree-1.0"

# UIA ControlType -> normalized cross-platform role
ROLE_MAP = {
    "Button": "button",
    "CheckBox": "checkbox",
    "ComboBox": "combobox",
    "DataGrid": "table",
    "DataItem": "table_cell",
    "Document": "document",
    "Edit": "text_field",
    "Group": "group",
    "Header": "header",
    "HeaderItem": "header_item",
    "Hyperlink": "link",
    "Image": "image",
    "List": "list",
    "ListItem": "list_item",
    "Menu": "menu",
    "MenuBar": "menu_bar",
    "MenuItem": "menu_item",
    "Pane": "pane",
    "ProgressBar": "progress_bar",
    "RadioButton": "radio_button",
    "ScrollBar": "scroll_bar",
    "Slider": "slider",
    "Spinner": "spinner",
    "SplitButton": "split_button",
    "StatusBar": "status_bar",
    "Tab": "tab_list",
    "TabItem": "tab",
    "Table": "table",
    "Text": "text",
    "Thumb": "thumb",
    "TitleBar": "title_bar",
    "ToolBar": "toolbar",
    "ToolTip": "tooltip",
    "Tree": "tree",
    "TreeItem": "tree_item",
    "Window": "window",
    "Custom": "custom",
}

# ControlType -> actions the element type claims (informational only;
# Gate 1 never invokes any of these)
ACTIONS_MAP = {
    "Button": ["invoke"],
    "CheckBox": ["toggle"],
    "ComboBox": ["expand", "select"],
    "Edit": ["set_value"],
    "Hyperlink": ["invoke"],
    "ListItem": ["select"],
    "MenuItem": ["invoke", "expand"],
    "RadioButton": ["select"],
    "Slider": ["set_value"],
    "Spinner": ["set_value"],
    "SplitButton": ["invoke", "expand"],
    "TabItem": ["select"],
    "TreeItem": ["select", "expand"],
}


def _is_password(info, name, automation_id):
    """Heuristic password detection. Never read values when in doubt."""
    try:
        # UIA IsPassword property via the raw element, when available
        raw = info.element
        # UIA_IsPasswordPropertyId = 30019
        val = raw.GetCurrentPropertyValue(30019)
        if val is True:
            return True
    except Exception:
        pass
    hay = f"{name or ''} {automation_id or ''}".lower()
    return "password" in hay or "passwd" in hay or "pwd" in hay


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def normalize_element(wrapper, node_id, pid, process):
    """Read-only property extraction. Never acts."""
    info = wrapper.element_info
    control_type = _safe(lambda: info.control_type, "Custom") or "Custom"
    name = _safe(lambda: info.name, "") or ""
    automation_id = _safe(lambda: info.automation_id, "") or ""
    enabled = bool(_safe(lambda: info.enabled, True))
    visible = bool(_safe(lambda: info.visible, True))

    pwd = _is_password(info, name, automation_id)
    value = None
    if not pwd and control_type in ("Edit", "ComboBox", "Text", "Document"):
        # Read-only value access on non-password text controls only
        value = _safe(lambda: info.rich_text or None)

    rect = _safe(lambda: wrapper.rectangle())
    rect_out = None
    if rect is not None:
        rect_out = {"x": rect.left, "y": rect.top,
                    "width": rect.width(), "height": rect.height(),
                    "informational_only": True}

    return {
        "id": node_id,
        "role": ROLE_MAP.get(control_type, "custom"),
        "name": name,
        "value": value,
        "description": "",
        "state": {
            "enabled": enabled,
            "visible": visible,
            "focused": False,   # focused-state tracking is a later gate
            "selected": None,
            "expanded": None,
            "checked": None,
            "modal": False,
            "loading": False,
        },
        "actions": ACTIONS_MAP.get(control_type, []),
        "rect": rect_out,
        "children": [],
        "platform": "windows-uia",
        "platform_native": {
            "automation_id": automation_id,
            "control_type": control_type,
            "class_name": _safe(lambda: info.class_name, "") or "",
            "process": process,
            "pid": pid,
        },
        "is_password": pwd,
    }


def dump_window(title=None, process=None, max_depth=12, max_nodes=2000):
    from pywinauto import Application  # noqa: E402  (import here: keeps module import side-effect free)

    criteria = {}
    if title:
        criteria["title"] = title
    if process:
        criteria["process"] = process
    if not criteria:
        return None, "no window selector given (need --title and/or --process)"

    try:
        app = Application(backend="uia").connect(**criteria)
    except Exception as e:
        return None, f"window not found: {e}"[:200]

    try:
        dlg = app.window(**criteria)
        pid = _safe(lambda: dlg.element_info.process_id)
        proc_name = process or _safe(lambda: dlg.element_info.framework_id, "")
    except Exception as e:
        return None, f"window inaccessible (possibly elevated): {e}"[:200]

    nodes = {}
    counter = [0]

    def walk(wrapper, depth):
        if depth > max_depth or counter[0] >= max_nodes:
            return None
        nid = f"n{counter[0]}"
        counter[0] += 1
        node = normalize_element(wrapper, nid, pid, proc_name or "")
        nodes[nid] = node
        if depth < max_depth:
            for child in _safe(lambda: wrapper.children(), []) or []:
                cid = walk(child, depth + 1)
                if cid:
                    node["children"].append(cid)
        return nid

    root_id = walk(dlg, 0)
    if root_id is None:
        return None, "failed to read window tree"
    return {
        "root": root_id,
        "nodes": nodes,
        "target": {"title": title, "process": proc_name, "pid": pid},
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default=None)
    ap.add_argument("--process", default=None)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--max-nodes", type=int, default=2000)
    args = ap.parse_args()

    t0 = time.time()
    result, err = dump_window(args.title, args.process,
                              args.max_depth, args.max_nodes)
    if result is None:
        code = 3 if err and "inaccessible" in err else 2
        sys.stderr.write(json.dumps({"error": err}) + "\n")
        return code

    import pywinauto
    raw_hash = hashlib.sha256(
        json.dumps(result["nodes"], sort_keys=True).encode()).hexdigest()
    artifact = {
        "schema": SCHEMA_VERSION,
        "provenance": {
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "capture_ms": round((time.time() - t0) * 1000, 1),
            "target": result["target"],
            "tool": "a11y_dump.py",
            "pywinauto_version": pywinauto.__version__,
            "backend": "uia",
            "tree_sha256": raw_hash,
            "observation_id": uuid.uuid4().hex,
            "read_only": True,
        },
        "root": result["root"],
        "nodes": result["nodes"],
    }
    sys.stdout.write(json.dumps(artifact))
    return 0


if __name__ == "__main__":
    sys.exit(main())
