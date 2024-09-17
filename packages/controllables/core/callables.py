r"""
Callables.
"""


import collections as _collections_
import itertools as _itertools_
import threading as _threading_
from typing import (
    Callable, 
    Generic, 
    Mapping, 
    NamedTuple,
    ParamSpec,
    TypeVar,
)

from .utils.containers import OrderedSet


ArgsT = ParamSpec('ArgsT')
RetT = TypeVar('RetT')


class ContinueOperation(Exception):
    r"""
    Signal that the current operation be continued.
    """

    pass

class StopOperation(Exception):
    r"""
    Signal that the current operation be stopped.
    """

    pass


class CallablePipeline(
    OrderedSet[Callable[ArgsT, RetT]],
    Callable[ArgsT, RetT],
    Generic[ArgsT, RetT],
):
    """
    A "multiplexing" callable for executing a sequence of callables.

    Examples:

    TODO
    """

    # TODO check ret Exception?
    def __call__(self, *args: ArgsT.args, **kwargs: ArgsT.kwargs) \
        -> Mapping[Callable[ArgsT, RetT], RetT]:
        r"""
        Execute the callback pipeline.
        Arguments are passed to callbacks in the pipeline.

        If a callback raises:
            * :class:`ContinueOperation`: 
                For the current call, the issuing callback is skipped 
                and its result not recorded in the return value.
                This is equivalent to a ``continue`` statement in a loop.
            * :class:`StopOperation`: 
                For the current call, all callbacks after 
                the issuing callback are skipped 
                and the return value contains only the results before
                the issuing callback.
                This is equivalent to a ``break`` statement in a loop.

        :returns: 
            The results of each callback, 
            keyed by the respective callback.
        """

        res = _collections_.OrderedDict()

        for f in self:
            try: 
                res[f] = f(*args, **kwargs)
            except ContinueOperation: continue
            except StopOperation: break

        return res
    

piped = CallablePipeline
r"""
Shortcut for creating a :class:`CallablePipeline`.
"""


class ExecutionContext(NamedTuple):
    r"""
    Execution context class.
    This represents the context in which a :class:`callable` is executed.
    """

    class Arguments(Generic[ArgsT]):
        r"""
        Arguments container class.
        This is a container for positional and keyword arguments
        that can be passed to a function.

        TODO docs
        """

        def __init__(self, *args: ArgsT.args, **kwargs: ArgsT.kwargs):
            self.__args__ = args
            self.__kwargs__ = kwargs

        def keys(self):
            return _itertools_.chain(
                range(len(self.__args__)),
                self.__kwargs__.keys(),
            )

        def values(self):
            return _itertools_.chain(
                self.__args__, 
                self.__kwargs__.values(),
            )
        
        def __iter__(self):
            return self.values()
        
        def __getitem__(self, key):
            if key in self.__args__:
                return self.__args__[key]
            return self.__kwargs__[key]

        def __repr__(self):
            args_r = str.join(', ', (repr(arg) for arg in self.__args__))
            kwargs_r = str.join(', ', 
                (f'{k}={v!r}' for k, v in self.__kwargs__.items()))
            return f'{self.__class__.__name__}({args_r}, {kwargs_r})'

    # TODO sync future?
    class Ack(Generic[RetT]):
        r"""
        Acknowledgement class.
        This represents an acknowledgement mechanism, 
        similar to `return` values in functions.
        """

        def __init__(self, deferred: bool = False):
            r"""
            Initialize the acknowledgement.

            :param deferred: 
                Whether to block :meth:`get` until :meth:`set` is called.
            """

            self.__value__: RetT | None = None
            self.__done__ = _threading_.Event() if deferred else None

        def set(self, value: RetT | None) -> RetT:
            r"""
            Set the acknowledgement value.
            In "deferred" mode, this will unblock :meth:`get` 
            if it is currently invoked.

            :param value: The value to set.
            :returns: The value set.
            """

            if self.__done__ is not None:
                self.__done__.set()
            self.__value__ = value
            return self.__value__
        
        def get(self, timeout: float | None = None) -> RetT:
            r"""
            Get the acknowledgement value.
            In "deferred" mode, this will block until 
            :meth:`set` is called.
            
            :param timeout: The timeout in seconds.
            :returns: The value set.
            """

            if self.__done__ is not None:
                self.__done__.wait(timeout=timeout)
                self.__done__.clear()
            return self.__value__
        
        def __call__(self, value: RetT | None = None) -> RetT:
            r"""
            Shortcut for :meth:`set`.

            .. seealso:: :meth:`set`
            """

            return self.set(value=value)
        
    vars: Arguments
    r"""
    The arguments passed to the :class:`callable`.
    Produced by the caller; consumed by the callee.
    """

    ack: Ack
    r"""
    The acknowledgement mechanism for the :class:`callable`.
    Produced by the callee; consumed by the caller.
    """


__all__ = [
    'ContinueOperation',
    'StopOperation',
    'CallablePipeline',
    'piped',
    'ExecutionContext',
]