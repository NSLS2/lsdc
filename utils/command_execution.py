from collections.abc import Callable, Mapping
from typing import TypeVar


Function = TypeVar("Function", bound=Callable[..., object])
_PARALLEL_SAFE_ATTRIBUTE = "_lsdc_safe_to_run_in_parallel"


def safe_to_run_in_parallel(func: Function) -> Function:
    setattr(func, _PARALLEL_SAFE_ATTRIBUTE, True)
    return func


def is_safe_to_run_in_parallel(
    command_name: str | None,
    functions: Mapping[str, Callable[..., object]],
) -> bool:
    func = functions.get(command_name) if command_name is not None else None
    return bool(func is not None and getattr(func, _PARALLEL_SAFE_ATTRIBUTE, False))
