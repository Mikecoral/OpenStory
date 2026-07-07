from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from worldkernel.architect.semantic.models import (
    FoundationBundle,
    ReferenceIndex,
    SemanticDomainArtifact,
    SemanticManifest,
)
from worldkernel.architect.semantic.storage import _default_output_root


class SemanticArtifactRepository:
    def __init__(self, world_id: str, root: str | Path | None = None) -> None:
        self.world_id = world_id
        self.root = Path(root) if root is not None else _default_output_root(world_id)

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def load_manifest(self) -> SemanticManifest:
        return SemanticManifest.model_validate(
            self._read_json(self.root / "metadata" / "semantic_manifest.json")
        )

    def load_reference_index(self) -> ReferenceIndex:
        return ReferenceIndex.model_validate(
            self._read_json(self.root / "metadata" / "reference_index.json")
        )

    def _load_domain(self, folder: str, file_name: str) -> SemanticDomainArtifact:
        return SemanticDomainArtifact.model_validate(self._read_json(self.root / folder / file_name))

    def load_locations(self) -> list[Any]:
        return self._load_domain("locations", "locations.json").items

    def load_characters(self) -> list[Any]:
        return self._load_domain("characters", "characters.json").items

    def load_path_graph(self) -> list[Any]:
        return self._load_domain("path_graph", "path_graph.json").items

    def load_relation_graph(self) -> list[Any]:
        return self._load_domain("relation_graph", "relation_graph.json").items

    def build_foundation_bundle(self) -> FoundationBundle:
        manifest = self.load_manifest()
        return FoundationBundle(
            world_id=self.world_id,
            locations=self.load_locations(),
            characters=self.load_characters(),
            path_graph=self.load_path_graph(),
            relation_graph=self.load_relation_graph(),
            constraints=manifest.constraints,
            provenance={"manifest": manifest.model_dump(mode="json")},
        )

    def get_location(self, location_id: str) -> dict[str, Any] | None:
        for item in self.load_locations():
            item_identity = item.get("identity", {}) if isinstance(item, dict) else {}
            candidate_id = item.get("id") if isinstance(item, dict) else None
            if not candidate_id and isinstance(item_identity, dict):
                candidate_id = item_identity.get("id")
            if candidate_id == location_id:
                return item
        return None

    def get_character(self, character_id: str) -> dict[str, Any] | None:
        for item in self.load_characters():
            item_identity = item.get("identity", {}) if isinstance(item, dict) else {}
            candidate_id = item.get("id") if isinstance(item, dict) else None
            if not candidate_id and isinstance(item_identity, dict):
                candidate_id = item_identity.get("id")
            if candidate_id == character_id:
                return item
        return None


def load_semantic_repository(
    world_id: str,
    output_root: str | Path | None = None,
) -> SemanticArtifactRepository:
    return SemanticArtifactRepository(world_id=world_id, root=output_root)
