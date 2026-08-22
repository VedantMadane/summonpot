"""Conservative type compatibility for bound arguments.

The rule throughout: **reject only provable incompatibility**, never the absence of
provable compatibility. An unresolved annotation, `Any`, a shape this module does not
model, or anything else it cannot decide is accepted. A guard that rejects a valid
declaration is worse than one that misses an invalid one, because the invalid one
still fails later with a real error while the valid one can never be written at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import UnionType
from typing import (
    Annotated,
    Any,
    Literal,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

# Shapes a model can be asked to select an item from. A string is iterable but its
# items are characters, and a mapping iterates its keys; neither is a collection of
# selectable values in the sense AgentChoice means.
_SELECTABLE_ORIGINS = (list, set, frozenset, tuple, Sequence)


def unwrap(annotation: Any) -> Any:
    """Strip `Annotated` down to the type it decorates."""
    while get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]
    return annotation


def _is_unknown(annotation: Any) -> bool:
    """Report whether nothing can be proven about this annotation."""
    if annotation is None or annotation is Any or annotation is object:
        return True
    # An unresolved forward reference, or a type variable with no binding here.
    return isinstance(annotation, str | TypeVar)


def _union_members(annotation: Any) -> tuple[Any, ...] | None:
    """Return a union's members, or None if this is not a union."""
    origin = get_origin(annotation)
    if origin is Union or origin is UnionType:
        return get_args(annotation)
    return None


def is_compatible(source: Any, target: Any) -> bool:
    """Report whether a value of type `source` may be passed where `target` is wanted.

    True also means "cannot be disproven". Only a definite mismatch returns False.
    """
    source, target = unwrap(source), unwrap(target)

    if _is_unknown(source) or _is_unknown(target):
        return True
    if source is target:
        return True

    # A union target is satisfied by matching any one member; a union source has to
    # be safe for every member, since any of them may arrive.
    target_members = _union_members(target)
    source_members = _union_members(source)
    if source_members is not None:
        return all(is_compatible(member, target) for member in source_members)
    if target_members is not None:
        return any(is_compatible(source, member) for member in target_members)

    if _is_literal(source):
        return all(is_compatible(type(value), target) for value in get_args(source))
    if _is_literal(target):
        return True  # a value-level constraint, not something a type can disprove

    source_origin, target_origin = get_origin(source), get_origin(target)
    if source_origin is not None or target_origin is not None:
        return _generics_compatible(source, target, source_origin, target_origin)

    if isinstance(source, type) and isinstance(target, type):
        if issubclass(source, target):
            return True
        # bool is an int, and int widens to float and complex, per the numeric tower.
        if source is int and target in (float, complex):
            return True
        return source is float and target is complex

    return True


def _is_literal(annotation: Any) -> bool:
    return get_origin(annotation) is Literal


def _generics_compatible(
    source: Any, target: Any, source_origin: Any, target_origin: Any
) -> bool:
    """Compare two annotations where at least one is parameterised.

    Only same-origin comparisons are decided; anything else is left unknown rather
    than guessed at.
    """
    if source_origin is None or target_origin is None:
        return True
    if source_origin is not target_origin:
        if isinstance(source_origin, type) and isinstance(target_origin, type):
            return issubclass(source_origin, target_origin)
        return True

    source_args, target_args = get_args(source), get_args(target)
    if not source_args or not target_args or len(source_args) != len(target_args):
        return True
    return all(
        is_compatible(s, t)
        for s, t in zip(source_args, target_args, strict=False)
        if s is not Ellipsis and t is not Ellipsis
    )


def selectable_item_type(output: Any) -> tuple[bool, Any]:
    """Describe what a model could select from a result of type `output`.

    Returns whether the shape is selectable at all, and the item type if it is known.
    """
    output = unwrap(output)
    if _is_unknown(output):
        return True, None

    origin = get_origin(output) or output
    if isinstance(origin, type) and issubclass(origin, (str, bytes, bytearray)):
        return False, None
    if isinstance(origin, type) and issubclass(origin, dict):
        return False, None
    if origin not in _SELECTABLE_ORIGINS and not (
        isinstance(origin, type)
        and any(
            isinstance(candidate, type) and issubclass(origin, candidate)
            for candidate in (list, set, frozenset, tuple)
        )
    ):
        return False, None

    args = [a for a in get_args(output) if a is not Ellipsis]
    return True, args[0] if args else None


def describe(annotation: Any) -> str:
    """Render an annotation for an error message."""
    annotation = unwrap(annotation)
    if annotation is None:
        return "unannotated"
    return getattr(annotation, "__name__", None) or str(annotation)
