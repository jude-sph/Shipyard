"""Consolidated agent tools — 7 tools for the MBSE modeling agent."""
from __future__ import annotations

from typing import Any

from src.core.models.core import ProjectModel, Link


# ---------------------------------------------------------------------------
# OpenAI function-calling format tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_project",
            "description": (
                "Flexible read tool for inspecting project data. Use scope to select "
                "what to query: summary, requirements, elements, links, coverage, "
                "batches, reference, or validation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": [
                            "summary", "requirements", "elements", "links",
                            "coverage", "batches", "reference", "validation",
                        ],
                        "description": "What to query.",
                    },
                    "filter": {
                        "type": "object",
                        "description": (
                            "Optional filters. For requirements: dig_id, id. "
                            "For elements: layer, collection, id. "
                            "For links: source_id, target_id, type. "
                            "For batches: batch_type."
                        ),
                    },
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trace",
            "description": (
                "Trace an ID (requirement or element) through the full chain: "
                "requirement -> links -> elements, or element -> links -> requirements."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The requirement or element ID to trace.",
                    },
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_decomposition",
            "description": (
                "Modify decomposition trees. Actions: edit, add, remove, re_decompose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["edit", "add", "remove", "re_decompose"],
                        "description": "The decomposition action to perform.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Action-specific parameters.",
                    },
                },
                "required": ["action", "params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_model",
            "description": (
                "Modify model elements and links. Actions: add_element, edit_element, "
                "remove_element, add_link, edit_link, remove_link, regenerate_layer, "
                "clear_layer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "add_element", "edit_element", "remove_element",
                            "add_link", "edit_link", "remove_link",
                            "regenerate_layer", "clear_layer",
                        ],
                        "description": "The model modification action.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Action-specific parameters.",
                    },
                },
                "required": ["action", "params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_queue",
            "description": (
                "Manage the modeling queue. Actions: send (add to queue), "
                "dismiss (move to dismissed), restore (remove from dismissed)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["send", "dismiss", "restore"],
                        "description": "Queue action.",
                    },
                    "req_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of requirement IDs to act on.",
                    },
                },
                "required": ["action", "req_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "batch_modify",
            "description": (
                "Execute a list of operations in sequence. Each operation specifies "
                "a tool name and arguments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool": {"type": "string"},
                                "args": {"type": "object"},
                            },
                            "required": ["tool", "args"],
                        },
                        "description": "List of operations with tool and args.",
                    },
                },
                "required": ["operations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate",
            "description": (
                "Validate the project. Scope: model (coverage + link integrity), "
                "decomposition (placeholder), all (both)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["model", "decomposition", "all"],
                        "description": "What to validate. Defaults to 'all'.",
                    },
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: iterate over all elements in the model
# ---------------------------------------------------------------------------


def _iter_elements(project: ProjectModel):
    """Yield (layer_key, collection_key, index, element_dict) for every element."""
    for layer_key, layer_value in project.layers.items():
        if not isinstance(layer_value, dict):
            continue
        for collection_key, collection in layer_value.items():
            if not isinstance(collection, list):
                continue
            for idx, element in enumerate(collection):
                if isinstance(element, dict):
                    yield layer_key, collection_key, idx, element


# ---------------------------------------------------------------------------
# Internal handlers
# ---------------------------------------------------------------------------


def _query_project(project: ProjectModel, scope: str, filter_params: dict | None = None) -> dict:
    f = filter_params or {}

    if scope == "summary":
        # Count elements per layer
        elements_per_layer: dict[str, int] = {}
        for layer_key, layer_value in project.layers.items():
            count = 0
            if isinstance(layer_value, dict):
                for coll in layer_value.values():
                    if isinstance(coll, list):
                        count += len(coll)
            elements_per_layer[layer_key] = count

        # Coverage
        linked_req_ids = set()
        for link in project.links:
            for req in project.requirements:
                if link.source == req.id or link.target == req.id:
                    linked_req_ids.add(req.id)
        total = len(project.requirements)
        covered = len(linked_req_ids)

        # Count decomposed DIGs
        decomposed_digs = len(project.decomposition_trees)

        return {
            "success": True,
            "data": {
                "requirements": total,
                "decomposed_digs": decomposed_digs,
                "elements_per_layer": elements_per_layer,
                "links": len(project.links),
                "coverage_percent": round(covered / total * 100) if total else 100,
            },
        }

    elif scope == "requirements":
        reqs = project.requirements
        if "dig_id" in f:
            reqs = [r for r in reqs if r.source_dig == f["dig_id"]]
        if "id" in f:
            reqs = [r for r in reqs if r.id == f["id"]]
        return {
            "success": True,
            "data": [{"id": r.id, "text": r.text, "source_dig": r.source_dig} for r in reqs],
        }

    elif scope == "elements":
        elements: list[dict] = []
        target_layer = f.get("layer")
        target_collection = f.get("collection")
        target_id = f.get("id")
        for lk, ck, _, elem in _iter_elements(project):
            if target_layer and lk != target_layer:
                continue
            if target_collection and ck != target_collection:
                continue
            if target_id and elem.get("id") != target_id:
                continue
            elements.append({**elem, "_layer": lk, "_collection": ck})
        return {"success": True, "data": elements}

    elif scope == "links":
        links = project.links
        if "source_id" in f:
            links = [l for l in links if l.source == f["source_id"]]
        if "target_id" in f:
            links = [l for l in links if l.target == f["target_id"]]
        if "type" in f:
            links = [l for l in links if l.type == f["type"]]
        return {
            "success": True,
            "data": [l.model_dump() for l in links],
        }

    elif scope == "coverage":
        req_links: dict[str, list[dict]] = {req.id: [] for req in project.requirements}
        for link in project.links:
            for req_id in req_links:
                if link.source == req_id or link.target == req_id:
                    req_links[req_id].append(link.model_dump())

        details = []
        for req in project.requirements:
            lnks = req_links.get(req.id, [])
            details.append({
                "requirement_id": req.id,
                "text": req.text[:150],
                "covered": len(lnks) > 0,
                "link_count": len(lnks),
                "links": lnks,
            })

        covered = sum(1 for d in details if d["covered"])
        return {
            "success": True,
            "data": {
                "total": len(details),
                "covered": covered,
                "uncovered": len(details) - covered,
                "percentage": round(covered / len(details) * 100) if details else 100,
                "details": details,
            },
        }

    elif scope == "batches":
        batches = project.batches
        if "batch_type" in f:
            batches = [b for b in batches if b.batch_type == f["batch_type"]]
        return {
            "success": True,
            "data": [b.model_dump(mode="json") for b in batches],
        }

    elif scope == "reference":
        return {
            "success": True,
            "data": project.reference_data or {},
        }

    elif scope == "validation":
        # Placeholder
        return {"success": True, "data": {}}

    return {"success": False, "message": f"Unknown scope '{scope}'."}


def _trace(project: ProjectModel, id: str) -> dict:
    # Find all links involving this ID
    related_links = [
        l for l in project.links
        if l.source == id or l.target == id
    ]

    if not related_links:
        return {"success": True, "data": {"id": id, "links": [], "connected": []}}

    # Gather connected IDs
    connected_ids = set()
    for link in related_links:
        if link.source != id:
            connected_ids.add(link.source)
        if link.target != id:
            connected_ids.add(link.target)

    # Resolve connected elements/requirements
    connected: list[dict] = []
    for cid in connected_ids:
        # Check requirements
        for req in project.requirements:
            if req.id == cid:
                connected.append({"id": cid, "type": "requirement", "text": req.text})
                break
        else:
            # Check elements
            for lk, ck, _, elem in _iter_elements(project):
                if elem.get("id") == cid:
                    connected.append({
                        "id": cid, "type": "element",
                        "layer": lk, "collection": ck, "name": elem.get("name", ""),
                    })
                    break

    return {
        "success": True,
        "data": {
            "id": id,
            "links": [l.model_dump() for l in related_links],
            "connected": connected,
        },
    }


def _modify_decomposition(project: ProjectModel, action: str, params: dict) -> dict:
    if action == "re_decompose":
        return {"success": False, "message": "re_decompose is not yet implemented."}

    trees = project.decomposition_trees
    dig_id = params.get("dig_id", "")

    if action == "add":
        tree_data = params.get("tree")
        if not dig_id or tree_data is None:
            return {"success": False, "message": "add requires dig_id and tree in params."}
        trees[dig_id] = tree_data
        return {"success": True, "message": f"Added decomposition tree for DIG '{dig_id}'."}

    elif action == "edit":
        if dig_id not in trees:
            return {"success": False, "message": f"No decomposition tree for DIG '{dig_id}'."}
        updates = params.get("updates", {})
        if isinstance(trees[dig_id], dict):
            trees[dig_id].update(updates)
        return {"success": True, "message": f"Updated decomposition tree for DIG '{dig_id}'."}

    elif action == "remove":
        if dig_id not in trees:
            return {"success": False, "message": f"No decomposition tree for DIG '{dig_id}'."}
        del trees[dig_id]
        return {"success": True, "message": f"Removed decomposition tree for DIG '{dig_id}'."}

    return {"success": False, "message": f"Unknown decomposition action '{action}'."}


def _modify_model(project: ProjectModel, action: str, params: dict) -> dict:
    if action == "add_element":
        layer = params.get("layer")
        collection = params.get("collection")
        element = params.get("element")

        if layer not in project.layers:
            return {"success": False, "message": f"Layer '{layer}' not found."}

        layer_data = project.layers[layer]
        if not isinstance(layer_data, dict):
            return {"success": False, "message": f"Layer '{layer}' is not a dict."}

        if collection not in layer_data:
            layer_data[collection] = []

        if not isinstance(layer_data[collection], list):
            return {"success": False, "message": f"Collection '{collection}' is not a list."}

        # Duplicate check
        new_id = element.get("id") if isinstance(element, dict) else None
        if new_id:
            for _, _, _, existing in _iter_elements(project):
                if existing.get("id") == new_id:
                    return {"success": False, "message": f"Element '{new_id}' already exists."}

        layer_data[collection].append(element)
        return {"success": True, "message": f"Added element to {layer}/{collection}."}

    elif action == "edit_element":
        element_id = params.get("element_id")
        updates = params.get("updates", {})

        for lk, ck, idx, elem in _iter_elements(project):
            if elem.get("id") == element_id:
                elem.update(updates)
                project.layers[lk][ck][idx] = elem
                return {"success": True, "message": f"Modified element '{element_id}'."}

        return {"success": False, "message": f"Element '{element_id}' not found."}

    elif action == "remove_element":
        element_id = params.get("element_id")
        cascade = params.get("cascade", False)

        found = False
        for lk, ck, idx, elem in _iter_elements(project):
            if elem.get("id") == element_id:
                project.layers[lk][ck].pop(idx)
                found = True
                break

        if not found:
            return {"success": False, "message": f"Element '{element_id}' not found."}

        removed_links = 0
        if cascade:
            before = len(project.links)
            project.links = [
                l for l in project.links
                if l.source != element_id and l.target != element_id
            ]
            removed_links = before - len(project.links)

        msg = f"Removed element '{element_id}'."
        if cascade:
            msg += f" Cascade-removed {removed_links} link(s)."
        return {"success": True, "message": msg}

    elif action == "add_link":
        link_data = params.get("link", {})
        for field in ("id", "source", "target", "type", "description"):
            if field not in link_data:
                return {"success": False, "message": f"Link missing field '{field}'."}

        for existing in project.links:
            if existing.id == link_data["id"]:
                return {"success": False, "message": f"Link '{link_data['id']}' already exists."}

        project.links.append(Link(
            id=link_data["id"],
            source=link_data["source"],
            target=link_data["target"],
            type=link_data["type"],
            description=link_data["description"],
        ))
        return {"success": True, "message": f"Added link '{link_data['id']}'."}

    elif action == "edit_link":
        link_id = params.get("link_id")
        updates = params.get("updates", {})

        for idx, link in enumerate(project.links):
            if link.id == link_id:
                link_dict = link.model_dump()
                link_dict.update(updates)
                project.links[idx] = Link(**link_dict)
                return {"success": True, "message": f"Modified link '{link_id}'."}

        return {"success": False, "message": f"Link '{link_id}' not found."}

    elif action == "remove_link":
        link_id = params.get("link_id")
        before = len(project.links)
        project.links = [l for l in project.links if l.id != link_id]
        if len(project.links) == before:
            return {"success": False, "message": f"Link '{link_id}' not found."}
        return {"success": True, "message": f"Removed link '{link_id}'."}

    elif action == "regenerate_layer":
        layer = params.get("layer")
        data = params.get("data")
        if layer not in project.layers:
            return {"success": False, "message": f"Layer '{layer}' not found."}
        project.layers[layer] = data
        return {"success": True, "message": f"Replaced layer '{layer}'."}

    elif action == "clear_layer":
        layer = params.get("layer")
        if layer not in project.layers:
            return {"success": False, "message": f"Layer '{layer}' not found."}
        layer_data = project.layers[layer]
        if isinstance(layer_data, dict):
            for key in layer_data:
                if isinstance(layer_data[key], list):
                    layer_data[key] = []
        return {"success": True, "message": f"Cleared layer '{layer}'."}

    return {"success": False, "message": f"Unknown model action '{action}'."}


def _manage_queue(project: ProjectModel, action: str, req_ids: list[str]) -> dict:
    if action == "send":
        added = []
        for rid in req_ids:
            if rid not in project.modeling_queue:
                project.modeling_queue.append(rid)
                added.append(rid)
        return {"success": True, "message": f"Added {len(added)} to modeling queue.", "added": added}

    elif action == "dismiss":
        dismissed = []
        for rid in req_ids:
            if rid not in project.dismissed_from_modeling:
                project.dismissed_from_modeling.append(rid)
                dismissed.append(rid)
            # Also remove from modeling queue if present
            if rid in project.modeling_queue:
                project.modeling_queue.remove(rid)
        return {"success": True, "message": f"Dismissed {len(dismissed)}.", "dismissed": dismissed}

    elif action == "restore":
        restored = []
        for rid in req_ids:
            if rid in project.dismissed_from_modeling:
                project.dismissed_from_modeling.remove(rid)
                restored.append(rid)
        return {"success": True, "message": f"Restored {len(restored)}.", "restored": restored}

    return {"success": False, "message": f"Unknown queue action '{action}'."}


def _batch_modify(project: ProjectModel, operations: list[dict]) -> dict:
    results = []
    for op in operations:
        tool = op.get("tool", "")
        args = op.get("args", {})
        result = apply_tool(project, tool, args)
        results.append({"tool": tool, "result": result})
        if not result.get("success"):
            return {
                "success": False,
                "message": f"Batch failed at operation: {tool}",
                "results": results,
            }
    return {"success": True, "message": f"Executed {len(results)} operations.", "results": results}


def _validate(project: ProjectModel, scope: str = "all") -> dict:
    data: dict[str, Any] = {}

    if scope in ("model", "all"):
        # Coverage check
        linked_req_ids = set()
        for link in project.links:
            for req in project.requirements:
                if link.source == req.id or link.target == req.id:
                    linked_req_ids.add(req.id)

        total = len(project.requirements)
        covered = len(linked_req_ids)
        uncovered_ids = [r.id for r in project.requirements if r.id not in linked_req_ids]

        # Orphaned links: links referencing IDs that don't exist as requirements or elements
        all_element_ids = {elem.get("id") for _, _, _, elem in _iter_elements(project)}
        all_req_ids = {r.id for r in project.requirements}
        known_ids = all_element_ids | all_req_ids

        orphaned = []
        for link in project.links:
            if link.source not in known_ids or link.target not in known_ids:
                orphaned.append(link.id)

        data["model"] = {
            "total_requirements": total,
            "covered": covered,
            "uncovered": total - covered,
            "uncovered_ids": uncovered_ids,
            "coverage_percent": round(covered / total * 100) if total else 100,
            "orphaned_links": orphaned,
        }

    if scope in ("decomposition", "all"):
        # Placeholder
        data["decomposition"] = {"status": "not_implemented"}

    return {"success": True, "data": data}


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "query_project": lambda p, args: _query_project(p, args["scope"], args.get("filter")),
    "trace": lambda p, args: _trace(p, args["id"]),
    "modify_decomposition": lambda p, args: _modify_decomposition(p, args["action"], args["params"]),
    "modify_model": lambda p, args: _modify_model(p, args["action"], args["params"]),
    "manage_queue": lambda p, args: _manage_queue(p, args["action"], args["req_ids"]),
    "batch_modify": lambda p, args: _batch_modify(p, args["operations"]),
    "validate": lambda p, args: _validate(p, args.get("scope", "all")),
}


def apply_tool(project: ProjectModel, tool_name: str, arguments: dict) -> dict:
    """Dispatch tool call to handler. Returns {success: bool, ...}."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"success": False, "message": f"Unknown tool '{tool_name}'."}
    try:
        return handler(project, arguments)
    except Exception as exc:
        return {"success": False, "message": f"Tool '{tool_name}' error: {exc}"}
