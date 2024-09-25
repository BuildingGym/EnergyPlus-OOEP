r"""
TODO
"""


import abc as _abc_
import functools as _functools_
import threading as _threading_
import warnings as _warnings_
from typing import (
    Any, 
    Callable,
    TypedDict, 
    Optional,
)

from ...errors import OptionalModuleNotFoundError
try: 
    import ray.rllib.env as _rayrl_env_
except ModuleNotFoundError as e:
    raise OptionalModuleNotFoundError.suggest(['ray[rllib]']) from e

from ...systems import BaseSystem 
from ...errors import TemporaryUnavailableError
from ...components import BaseComponent
from ...variables import (
    BaseVariable, 
    BaseMutableVariable,
)
from ...callbacks import Callback
from ..gymnasium.env import _TODO_rm_Agent, _TODO_rm_AgentManager


# TODO callback interface??
class BaseEnvEpisodeController(
    BaseComponent[
        _rayrl_env_.ExternalEnv 
        | _rayrl_env_.ExternalMultiAgentEnv
    ],
    _abc_.ABC,
):
    r"""
    
    .. code-block:: python
        env: ray.rllib.ExternalEnv = ...

        with env.track_episode() as episode:
            episode.step()

    """

    def __init__(self):
        self._episode_id = None

    @property
    def started(self):
        return self._episode_id is not None

    def start(self, training_enabled=True):
        if self._episode_id is not None:
            return 
        
        self._episode_id = self._manager.start_episode(
            training_enabled=training_enabled,
        )

        return self
    
    def end(self, observation=None):    
        if self._episode_id is None:
            return

        if isinstance(self._manager, _rayrl_env_.ExternalMultiAgentEnv):
            self._manager.end_episode(
                self._episode_id, 
                observation_dict=observation,
            )
        else:
            self._manager.end_episode(
                self._episode_id, 
                observation=observation,
            )
        self._episode_id = None

        return self

    def __enter__(self):
        return self.start()
    
    def __exit__(self, exc_type, exc_value, traceback):
        exc_type, exc_value, traceback
        return self.end()
    
    @_abc_.abstractmethod
    def step(self):
        ...

    def log_returns(
        self, 
        reward=None, info=None, 
    ):
        r"""
        TODO doc
        bail if no rewards
        """

        if self._episode_id is None:
            raise RuntimeError('TODO')

        if isinstance(self._manager, _rayrl_env_.ExternalMultiAgentEnv):
            return self._manager.log_returns(
                self._episode_id,
                reward_dict=reward,
                info_dict=info,
            )
        return self._manager.log_returns(
            self._episode_id,
            reward=reward,
            info=info,
        )
    
    def get_action(self, observation=None):
        r"""
        TODO doc
        bail if no observations
        """

        if self._episode_id is None:
            raise RuntimeError('TODO')

        if isinstance(self._manager, _rayrl_env_.ExternalMultiAgentEnv):
            return self._manager.get_action(
                self._episode_id, 
                observation_dict=observation,
            )
        return self._manager.get_action(
            self._episode_id, 
            observation=observation,
        )


class CommonEnv(
    _rayrl_env_.ExternalEnv,
    BaseComponent[BaseSystem],
    _abc_.ABC,
):
    class Config(TypedDict):
        r"""
        Configuration for external environment 
        attached to a system.
        """

        system: Optional[
            BaseSystem 
            | Callable[[], BaseSystem]
        ]
        r"""
        Reference to the system to attach to.
        Can either be a system instance or 
        a :class:`callable` that returns a system instance.
        If not specified, the system must be 
        :meth:`__attach__`-ed manually
        before anything can be done with the environment.

        .. seealso:: :meth:`ExternalEnv.__attach__`
        """
        system_mgmt_enabled: Optional[bool]
        r"""
        Whether to manage the system internally - God mode.
        If :class:`True`, the environment will `start`/`stop` the system
        automatically when the environment is `run`/`join`-ed.

        Useful when the environment needs to run in distributed settings,
        where the system cannot be shared among the nodes/workers.
        """

        class EpisodeEvents(TypedDict):
            r"""Episode events."""

            RefT = Any | Callback
            r"""Reference type. TODO doc"""

            start: Optional[RefT | None]
            r"""Reference to start the episode."""

            end: Optional[RefT | None]
            r"""Reference to end the started episode."""

            step: Optional[RefT | None]
            r"""Reference to step the started episode."""

        episode_events: Optional[EpisodeEvents]
        r"""Episode events."""

    def __init__(self, config: Config):
        self._config = config

    @_functools_.cached_property
    def _thread_locker(self):
        return _threading_.Event()
    
    @property
    @_abc_.abstractmethod
    def action(self) -> BaseMutableVariable | None: ...
    
    @property
    @_abc_.abstractmethod
    def observation(self) -> BaseVariable | None: ...

    @property
    @_abc_.abstractmethod
    def reward(self) -> BaseVariable | None: ...

    @property
    @_abc_.abstractmethod
    def info(self) -> BaseVariable | None: ...

    class EpisodeController(
        BaseEnvEpisodeController,
        BaseComponent['CommonEnv'],
    ):
        _manager: 'CommonEnv'

        def start(self, training_enabled=True):
            return super().start(
                training_enabled=training_enabled,
            )

        def end(self, observation=None):
            if observation is None:
                try: observation = self._manager.observation.value
                # TODO panic?????
                except TemporaryUnavailableError as e: 
                    _warnings_.warn(
                        f'Observation required to end the episode; got {e!r}',
                        RuntimeWarning,
                    )
                    #raise ValueError('Observation required to end the episode; got none')
                    return
            return super().end(observation=observation)

        def step(self):
            if not self.started:
                return
            try:
                self.log_returns()
                if self._manager.action is not None:
                    self._manager.action.value = self.get_action()
            except TemporaryUnavailableError: pass

        def log_returns(self, reward=None, info=None):
            # TODO try/except
            if reward is None and self._manager.reward is not None:
                reward = self._manager.reward.value
            if info is None and self._manager.info is not None:
                info = self._manager.info.value
            return super().log_returns(reward=reward, info=info)
        
        def get_action(self, observation=None):
            if observation is None and self._manager.observation is not None:
                observation = self._manager.observation.value
            return super().get_action(observation=observation)

    def episode_controller(self):
        r"""
        TODO doc
        """

        return self.EpisodeController().__attach__(self)

    def run(self):
        r"""
        TODO doc
        
        """

        if (system := self._config.get('system')) is not None:
            if isinstance(system, BaseSystem):
                self.__attach__(system)
            elif isinstance(system, Callable):
                self.__attach__(system())
            else:
                raise TypeError(f'Invalid `{BaseSystem}` reference type: {type(system)}')

        def setup():
            if self._manager is None:
                raise RuntimeError(
                    f'Cannot run without a `{BaseSystem}` `{self.__attach__}`-ed'
                )
            
            events = self._manager.events
            
            episode_events: CommonEnv.Config.EpisodeEvents = {
                'start': events['begin'] if 'begin' in events else None,
                'end': events['end'] if 'end' in events else None,                
                'step': events['timestep'] if 'timestep' in events else None,                
                **self._config.get('episode_events', dict()),
            }

            def _get_callback(o) -> Callback:
                if isinstance(o, Callback):
                    return o
                return self._manager.events[o]

            # TODO bridge callbacks: .on(<Callback instance>)
            tracker = self.episode_controller()
            for key, callback in [
                ('start', lambda *args, **kwargs: tracker.start()),
                ('end', lambda *args, **kwargs: tracker.end()),
                ('step', lambda *args, **kwargs: tracker.step()),
            ]:
                if episode_events.get(key) is not None:
                    _get_callback(episode_events[key]).on(callback)

        # TODO teardown afterwards OR subevent/subvariables!!!
        setup()
        # TODO self.__attach__.on(lambda _: setup())
        #self._TODO_workflows.on('attach', setup)
        
        if self._config.get('system_mgmt_enabled'):
            self._manager.run()
        else: self._thread_locker.wait()

    def join(self, timeout=None):
        r"""
        TODO doc
        
        """

        if self._config.get('system_mgmt_enabled'):
            self._manager.stop()
        else: self._thread_locker.set()
        return super().join(timeout=timeout)


# TODO !!!!
class ExternalMultiAgentEnv(
    CommonEnv,
    _rayrl_env_.ExternalMultiAgentEnv,
):
    class Config(_TODO_rm_AgentManager.Config, CommonEnv.Config):
        pass
        
    # TODO
    def __init__(self, config: Config):
        _rayrl_env_.ExternalMultiAgentEnv.__init__(
            self,
            action_space=config['action_space'],
            observation_space=config['observation_space'],
        )
        CommonEnv.__init__(self, config=config)
        self._agents = _TODO_rm_AgentManager(config=config)

    def __attach__(self, manager):
        CommonEnv.__attach__(self, manager)
        self._agents.__attach__(self._manager)
        return self
    
    @property
    def action(self): 
        return self._agents.actions
    
    @property
    def observation(self): 
        return self._agents.observations
    
    @property
    def reward(self): 
        return self._agents.rewards
    
    @property
    def info(self): 
        return self._agents.infos


# TODO
class ExternalEnv(
    CommonEnv,
    _rayrl_env_.ExternalEnv, 
):
    r"""
    A Ray RLlib external environment for interfacing with worlds.

    TODO examples

    .. seealso::
    * `ray.rllib.ExternalEnv <https://docs.ray.io/en/latest/rllib/package_ref/env/external_env.html#rllib-env-external-env-externalenv>`_
    """

    class Config(_TODO_rm_Agent.Config, CommonEnv.Config):
        pass
        
    # TODO
    def __init__(self, config: Config):
        _rayrl_env_.ExternalEnv.__init__(
            self,
            action_space=config['action_space'],
            observation_space=config['observation_space'],
        )
        CommonEnv.__init__(self, config=config)
        self._agents = _TODO_rm_AgentManager(_TODO_rm_AgentManager.Config(
            action_space={None: config['action_space']},
            observation_space={None: config['observation_space']},
            reward_function={None: config.get('reward_function')},
            info_function={None: config.get('info_function')},
        ))

    def __attach__(self, manager):
        CommonEnv.__attach__(self, manager)
        self._agents.__attach__(self._manager)
        return self
    
    @property
    def action(self): 
        return self._agents[None].action
    
    @property
    def observation(self): 
        return self._agents[None].observation
    
    @property
    def reward(self): 
        return self._agents[None].reward
    
    @property
    def info(self): 
        return self._agents[None].info


__all__ = [
    'ExternalMultiAgentEnv',
    'ExternalEnv',
]