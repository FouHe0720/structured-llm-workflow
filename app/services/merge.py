"""Deterministic conflict preservation rather than allowing a reducer to invent facts."""

from app.domain.models import Conflict, StrictModel


def merge_extractions(
    values: list[StrictModel], schema: type[StrictModel]
) -> tuple[StrictModel, list[Conflict]]:
    merged = {}
    conflicts = []
    for key in schema.model_fields:
        items = [v.model_dump()[key] for v in values]
        if all(isinstance(item, list) for item in items):
            merged[key] = list(dict.fromkeys(value for item in items for value in item))
        else:
            unique = list(dict.fromkeys(item for item in items if item is not None))
            merged[key] = unique[0] if len(unique) == 1 else None
            if len(unique) > 1:
                conflicts.append(Conflict(field=key, values=unique))
    return schema.model_validate(merged), conflicts
