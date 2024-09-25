r"""
Systems.

Scope: "And-God-said"s, "Let-there-be"s. (Genesis 1)
"""


import functools as _functools_
import os as _os_
import threading as _threading_
from typing import (
    Dict,
    Literal,
    Optional,
    Self,
    TypedDict,
    Unpack,
)

from controllables.core.systems import BaseSystem, SystemShortcutMixin
from controllables.core.components import BaseComponent

from ._core import Core
from .models.building import BuildingModel
from .models.weather import WeatherModel


class System(SystemShortcutMixin, BaseSystem):
    r"""
    TODO
    """

    # TODO
    class Config(TypedDict, total=False):
        building: BuildingModel | _os_.PathLike | None
        r"""The building model or the path to the building model."""

        weather: Optional[WeatherModel | _os_.PathLike | None]
        r"""The weather model or the path to the weather model."""

        report: Optional[_os_.PathLike | None]
        r"""The path to the report to generate."""

        design_day: Optional[bool | None]
        r"""
        Whether to run in design day mode.

        ..seealso:: https://energyplus.readthedocs.io/en/latest/tips_and_tricks/tips_and_tricks.html#design-day-creation
        """

        # TODO typing
        repeat: Optional[bool | float | None]
        r"""
        TODO Whether to run repeatedly.
        If number-like, the maximum number of runs.
        """
        
    def __init__(
        self, 
        building: BuildingModel | _os_.PathLike = None, 
        config: Config = Config(),
        **config_kwds: Unpack[Config],
    ):
        r"""
        Initialize a new building.

        TODO doc!!!
        :param building: The building model or the path to the building model.
        :param config: The specifications for the world. 
        :param **config_kwds: Entries to override in supplied :param:`config`.
        """
                
        self._config = self.Config({
            'building': building,
            **config,
            **config_kwds,
        })

    @_functools_.cached_property
    def _core(self):
        return Core()
    
    class _CoreThread(_threading_.Thread):
        def __init__(
            self, 
            core: Core, 
            cli_args: list[str], 
            iterations: float,
        ):
            super().__init__()
            self._core = core
            self._cli_args = cli_args
            self._iterations = iterations

        def run(self):
            while self._iterations > 0:
                self._iterations -= 1
                self._core.reset()
                self._core.configure(print_output=False)
                status = self._core.run(args=self._cli_args)
                if status != 0:
                    raise RuntimeError(
                        f'{self!r}: Operation failed with status {status}'
                    )

        def kill(self):
            r"""Signal the thread to stop."""

            self._iterations = 0
            self._core.stop()

    @_functools_.cached_property
    def _thread(self):
        import tempfile as _tempfile_
        import pathlib as _pathlib_

        c = self._config

        if c.get('building') is None:
            raise ValueError(f'Building model is required in {self.Config}')

        args = [
            # 0
            str(
                BuildingModel(c['building']).dumpf(
                    _tempfile_.NamedTemporaryFile(suffix='.epJSON').name,
                    format='json',
                ) 
                if isinstance(c['building'], (BuildingModel, Dict)) else
                _pathlib_.Path(c['building'])
            ),
            # "--output-directory"
            '--output-directory', 
            str(
                # TODO
                c['report']
            ) 
            if c.get('report') is not None else 
            _tempfile_.TemporaryDirectory(
                prefix='.energyplus_output_',
            ).name,
        ]
        if c.get('weather') is not None:
            args.extend([
                '--weather', str(
                    c['weather'].path
                    if isinstance(c['weather'], WeatherModel) else
                    c['weather']
                ),
            ])
        if c.get('design_day') is True:
            args.extend(['--design-day'])

        iterations = c.get('repeat')
        match c.get('repeat'):
            case False | None:
                iterations = 1
            case True:
                iterations = float('inf')

        return self._CoreThread(
            core=self._core,
            cli_args=args, 
            iterations=iterations,
        )

    def start(self):
        if self._thread.is_alive():
            raise RuntimeError(f'{self!r} is already running')
        del self._thread
        self._thread.start()
        return self
    
    @property
    def started(self):
        return self._thread.is_alive()    

    def wait(self, timeout=None):
        self._thread.join(timeout=timeout)
        return self
    
    # TODO __await__?

    def stop(self):
        if not self._thread.is_alive():
            raise RuntimeError(f'{self!r} is not running')
        self._thread.kill()
        return self

    @_functools_.cached_property
    def events(self):
        from .events import EventManager
        return EventManager().__attach__(self)

    @_functools_.cached_property
    def variables(self):
        from .variables import VariableManager
        return VariableManager().__attach__(self)
    
    def add(
        self, 
        component: BaseComponent[Self] 
            | Literal['logging:message', 'logging:progress']
    ):
        match component:
            case 'logging:message':
                from .logging.message import MessageLogger
                component = MessageLogger()
            case 'logging:progress':
                from .logging.progress import ProgressLogger
                component = ProgressLogger()
            case _:
                pass
        return super().add(component)

    def __getstate__(self) -> Config:
        return self._config
    
    def __setstate__(self, config: Config):
        self.__init__(config=config)


__all__ = [
    'System',
]