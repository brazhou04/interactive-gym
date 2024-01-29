import collections
import dataclasses
import queue
import threading
import typing
import numpy as np

from configurations import remote_config
from server import utils
from absl import logging


@dataclasses.dataclass(frozen=True)
class GameStatus:
    Done = "done"
    Active = "active"
    Inactive = "inactive"
    Reset = "reset"


@dataclasses.dataclass(frozen=True)
class PolicyTypes:
    Human = "human"
    Random = "random"


class RemoteGame:
    def __init__(self, config: remote_config.RemoteConfig, game_id: int):
        self.config = config
        self.status = GameStatus.Inactive
        self.lock = threading.Lock()
        self.reset_event = threading.Event()

        # Players and actions
        self.pending_actions = None
        self.reset_pending_actions()
        self.human_players = {}
        self.bot_players = {}
        self.bot_threads = {}

        # Game environment
        self.env = None
        self.obs: np.ndarray | dict[str, typing.Any] | None = None
        self.game_id = game_id
        self.tick_num = 0
        self.episode_num = 0

        self._build()

    def _build_env(self) -> None:
        self.env = self.config.env_creator(**self.config.env_config)

    def _load_policies(self) -> None:
        """Load and instantiates all policies"""
        for agent_id, policy_id in self.config.policy_mapping.items():
            if policy_id == PolicyTypes.Human:
                self.human_players[agent_id] = utils.Available
            elif policy_id == PolicyTypes.Random:
                self.bot_players[agent_id] = policy_id
            else:
                assert (
                    self.config.load_policy_fn is not None
                ), "Must provide a method to load policies via policy name to RemoteConfig!"
                self.bot_players[agent_id] = self.config.load_policy_fn(policy_id)

    def get_available_human_player_ids(self) -> list[str]:
        """List the available human player IDs"""
        return [
            pid
            for pid, player in self.human_players.items()
            if player is utils.Available
        ]

    def is_at_player_capacity(self) -> bool:
        """Check if there are any available human player IDs."""
        return not self.get_available_human_player_ids()

    def cur_num_human_players(self) -> int:
        return len(
            [pid for pid, sid in self.human_players.items() if sid != utils.Available]
        )

    def remove_human_player(self, subject_id) -> None:
        """Remove a human player from the game"""
        player_id = None
        for pid, sid in self.human_players.items():
            if subject_id == sid:
                player_id = pid
                break

        if player_id is None:
            logging.warning(
                f"Attempted to remove {subject_id} but player wasn't found."
            )
            return

        self.human_players[player_id] = utils.Available

    def is_ready_to_start(self) -> bool:
        ready = self.is_at_player_capacity()
        return ready

    def _build(self):
        self._build_env()
        self._load_policies()

    def tear_down(self):
        self.status = GameStatus.Inactive
        for q in self.pending_actions.values():
            q.queue.clear()

    def enqueue_action(self, subject_id, action) -> None:
        """Queue an action for a human player"""
        if self.status != GameStatus.Active:
            return

        if subject_id not in self.human_players.values():
            return

        try:
            self.pending_actions[subject_id].put(action)
        except queue.Full:
            pass

    def add_player(self, player_id: str | int, identifier: str | int) -> None:
        available_ids = self.get_available_human_player_ids()
        assert (
            player_id in available_ids
        ), f"Player ID is not available! Available IDs are: {available_ids}"

        self.human_players[player_id] = identifier

    def tick(self) -> None:
        # Player actions
        player_actions = {
            pid: self.pending_actions[sid].get(block=False)
            if self.pending_actions[sid].qsize() > 0
            else self.config.default_action
            for pid, sid in self.human_players.items()
        }

        # # bot actions
        # bot_actions = {
        #     pid: self.config.policy_inference_fn(self.obs[pid], bot)
        #     if self.tick_num % self.config.frame_skip == 0 and bot != PolicyTypes.Random
        #     else self.config.default_action
        #     for pid, bot in self.bot_players.items()
        # }

        # TODO(chase): add frame skip! also we shouldn't use default action on frame skip! should just repeat the last action
        for pid, bot in self.bot_players.items():
            if bot == PolicyTypes.Random:
                player_actions[pid] = self.env.action_space.sample()
            else:
                player_actions[pid] = self.config.policy_inference_fn(
                    self.obs[pid], bot
                )

        if len(player_actions) == 1:
            # not multiagent
            player_actions = list(player_actions.values())[0]

        self.obs, rewards, terminateds, truncateds, _ = self.env.step(player_actions)

        if isinstance(terminateds, dict):
            terminateds = terminateds["__all__"]
            truncateds = truncateds["__all__"]

        self.tick_num += 1
        if terminateds or truncateds:
            if self.episode_num < self.config.num_episodes:
                self.status = GameStatus.Reset
            else:
                self.status = GameStatus.Done

    def reset_pending_actions(self) -> None:
        self.pending_actions = collections.defaultdict(lambda: queue.Queue(maxsize=1))

    def reset(self, seed: int | None = None) -> None:
        self.reset_pending_actions()
        self.obs, _ = self.env.reset(seed=seed)
        self.status = GameStatus.Active
        self.tick_num = 0
        self.episode_num += 1
