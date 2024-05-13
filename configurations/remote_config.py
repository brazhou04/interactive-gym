import copy
import json
import typing

from configurations import configuration_constants


class RemoteConfig:
    """The RemoteConfig class is used to configure all settings for the interactive task."""

    def __init__(self):
        self.env_creator: typing.Callable | None = None
        self.env_name: str | None = None
        self.env_config: dict[str, typing.Any] = {}
        self.seed: int = 42

        # hosting
        self.host = None
        self.port = 8000
        self.max_concurrent_games = 1

        # policies
        self.load_policy_fn: typing.Callable | None = None
        self.policy_inference_fn: typing.Callable | None = None
        self.policy_mapping: dict[str, typing.Any] = dict()
        self.available_policies: dict[str, typing.Any] = dict()
        self.policy_configs: dict[str, typing.Any] = dict()
        self.frame_skip: int = 4

        # gameplay
        self.num_episodes: int = 1
        self.action_mapping: dict[str, int] = dict()
        self.human_id: str | int | None = None
        self.default_action: int | str | None = None
        self.action_population_method: str = (
            configuration_constants.ActionSettings.DefaultAction
        )
        self.input_mode: str = configuration_constants.InputModes.PressedKeys
        self.game_has_composite_actions: bool = False
        self.max_ping: int | None = None
        self.min_ping_measurements: int = 5
        self.callback: None = (
            None  # TODO(chase): add callback typehint but need to avoid circular import
        )

        # rendering
        self.env_to_state_fn: typing.Callable | None = None
        self.preload_specs: list[dict[str, str | int | float]] | None = None
        self.hud_text_fn: typing.Callable | None = None
        self.location_representation: str = "relative"  # "relative" or "pixels"
        self.game_width: int | None = 600
        self.game_height: int | None = 400
        self.fps: int = 10
        self.background: str = "#FFFFFF"  # white background default
        self.state_init: list = []
        self.assets_dir: str = "./static/assets/"
        self.assets_to_preload: list[str] = []
        self.animation_configs: list = []

        # user_experience
        self.end_game_redirect_url: str | None = (
            None  # send user here after experiment.
        )
        self.waitroom_timeout_redirect_url: str | None = (
            None  # here if waiting room times out
        )
        self.append_subject_name_to_redirect: bool = False
        self.redirect_timeout: int = 5_000  # 5k ms = 5 seconds default
        self.instructions_html_file: str | None = None
        self.waitroom_time_randomization_interval_s: tuple[int, int] = (0, 0)
        self.page_title: str = "interactive-gym"
        self.game_header_text: str = ""
        self.welcome_header_text: str = ""
        self.welcome_text: str = ""
        self.game_page_text: str = ""
        self.game_page_html_fn: typing.Callable | None = None
        self.between_episode_header: str = ""
        self.between_episode_text: str = ""
        self.final_page_text: str = ""
        self.final_page_header_text: str = ""
        self.instructions: str = ""  # can pass html
        self.reset_timeout: int = 3000

        # logging
        self.logfile: str = "./log"

    def logging(self, logfile: str | None = None) -> "RemoteConfig":
        """Set the settings for logging.

        :param logfile: The .log file to log to, defaults to None
        :type logfile: str | None, optional
        """
        if logfile is not None:
            self.logfile = logfile

    def environment(
        self,
        env_creator: typing.Callable | None = None,
        env_name: str | None = None,
        env_config: dict[str, typing.Any] | None = None,
        seed: int | None = None,
    ) -> "RemoteConfig":
        """Set the environment settings.

        :param env_creator: A function that returns an instance of the environment, defaults to None
        :type env_creator: typing.Callable | None, optional
        :param env_name: The name of the environment, defaults to None
        :type env_name: str | None, optional
        :param env_config: The configuration to pass to the environment on initialization, defaults to None
        :type env_config: dict[str, typing.Any] | None, optional
        :param seed: Random seed to use for the environment, defaults to None
        :type seed: int | None, optional
        :return: The RemoteConfig instance.
        :rtype: RemoteConfig
        """
        if env_creator is not None:
            self.env_creator = env_creator

        if env_name is not None:
            self.env_name = env_name

        if env_config is not None:
            self.env_config = env_config

        if seed is not None:
            self.seed = seed

        return self

    def rendering(
        self,
        fps: int | None = None,
        env_to_state_fn: typing.Callable | None = None,
        preload_specs: list[dict[str, str | float | int]] | None = None,
        hud_text_fn: typing.Callable | None = None,
        location_representation: str | None = None,
        game_width: int | None = None,
        game_height: int | None = None,
        background: str | None = None,
        state_init: list | None = None,
        assets_dir: str | None = None,
        assets_to_preload: list[str] | None = None,
        animation_configs: list | None = None,
    ) -> "RemoteConfig":
        """_summary_

        :param fps: _description_, defaults to None
        :type fps: int | None, optional
        :param env_to_state_fn: _description_, defaults to None
        :type env_to_state_fn: typing.Callable | None, optional
        :param preload_specs: _description_, defaults to None
        :type preload_specs: list[dict[str, str  |  float  |  int]] | None, optional
        :param hud_text_fn: _description_, defaults to None
        :type hud_text_fn: typing.Callable | None, optional
        :param location_representation: _description_, defaults to None
        :type location_representation: str | None, optional
        :param game_width: _description_, defaults to None
        :type game_width: int | None, optional
        :param game_height: _description_, defaults to None
        :type game_height: int | None, optional
        :param background: _description_, defaults to None
        :type background: str | None, optional
        :param state_init: _description_, defaults to None
        :type state_init: list | None, optional
        :param assets_dir: _description_, defaults to None
        :type assets_dir: str | None, optional
        :param assets_to_preload: _description_, defaults to None
        :type assets_to_preload: list[str] | None, optional
        :param animation_configs: _description_, defaults to None
        :type animation_configs: list | None, optional
        :return: _description_
        :rtype: RemoteConfig
        """
        if env_to_state_fn is not None:
            self.env_to_state_fn = env_to_state_fn

        if hud_text_fn is not None:
            self.hud_text_fn = hud_text_fn

        if preload_specs is not None:
            self.preload_specs = preload_specs

        if location_representation is not None:
            assert location_representation in [
                "relative",
                "pixels",
            ], "Must pass either relative or pixel location!"
            self.location_representation = location_representation

        if fps is not None:
            self.fps = fps

        if game_width is not None:
            self.game_width = game_width

        if game_height is not None:
            self.game_height = game_height

        if background is not None:
            self.background = background

        if state_init is not None:
            self.state_init = state_init

        if assets_dir is not None:
            self.assets_dir = assets_dir

        if assets_to_preload is not None:
            self.assets_to_preload = assets_to_preload

        if animation_configs is not None:
            self.animation_configs = animation_configs

        return self

    def hosting(
        self,
        host: str | None = None,
        port: int | None = None,
        max_concurrent_games: int | None = None,
        max_ping: int | None = None,
    ):
        if host is not None:
            self.host = host

        if port is not None:
            self.port = port

        if max_concurrent_games is not None:
            assert (
                max_concurrent_games >= 1
            ), "Must have at least one concurrent game!"
            self.max_concurrent_games = max_concurrent_games

        if max_ping is not None:
            self.max_ping = max_ping

        return self

    def policies(
        self,
        policy_mapping: dict | None = None,
        load_policy_fn: typing.Callable | None = None,
        policy_inference_fn: typing.Callable | None = None,
        frame_skip: int | None = None,
    ):
        if policy_mapping is not None:
            self.policy_mapping = policy_mapping

        if load_policy_fn is not None:
            self.load_policy_fn = load_policy_fn

        if policy_inference_fn is not None:
            self.policy_inference_fn = policy_inference_fn

        if frame_skip is not None:
            self.frame_skip = frame_skip

        return self

    def gameplay(
        self,
        action_mapping: dict | None = None,
        human_id: str | int | None = None,
        num_episodes: int | None = None,
        default_action: int | str | None = None,
        action_population_method: str | None = None,
        input_mode: str | None = None,
        callback: None = None,  # TODO(chase): add callback typehint without circular import
    ):
        if action_mapping is not None:
            # ensure the composite action tuples are sorted
            sorted_tuple_action_map = {}
            for k, v in action_mapping.items():
                if isinstance(k, tuple):
                    self.game_has_composite_actions = True
                    sorted_tuple_action_map[tuple(sorted(k))] = v
                else:
                    sorted_tuple_action_map[k] = v
            self.action_mapping = action_mapping

        if action_population_method is not None:
            self.action_population_method = action_population_method

        if human_id is not None:
            self.human_id = human_id

        if num_episodes is not None:
            assert (
                type(num_episodes) == int and num_episodes >= 1
            ), "Must pass an int >=1 to num episodes."
            self.num_episodes = num_episodes

        if default_action is not None:
            self.default_action = default_action

        if input_mode is not None:
            self.input_mode = input_mode

        if callback is not None:
            self.callback = callback

        return self

    def user_experience(
        self,
        page_title: str | None = None,
        instructions_html_file: str | None = None,
        end_game_redirect_url: str | None = None,
        waitroom_timeout_redirect_url: str | None = None,
        append_subject_name_to_redirect: bool | None = None,
        redirect_timeout: int | None = None,
        waitroom_timeout: tuple[int, int] | None = None,
        waitroom_time_randomization_interval_s: int | None = None,
        welcome_header_text: str | None = None,
        game_header_text: str | None = None,
        game_page_html_fn: typing.Callable | None = None,
        game_page_text: str | None = None,
        welcome_text: str | None = None,
        final_page_header_text: str | None = None,
        final_page_text: str | None = None,
        instructions: str | None = None,
    ):
        if end_game_redirect_url is not None:
            self.end_game_redirect_url = end_game_redirect_url

        if waitroom_timeout_redirect_url is not None:
            self.waitroom_timeout_redirect_url = waitroom_timeout_redirect_url

        if append_subject_name_to_redirect is not None:
            self.append_subject_name_to_redirect = (
                append_subject_name_to_redirect
            )

        if game_page_html_fn is not None:
            self.game_page_html_fn = game_page_html_fn

        if redirect_timeout is not None:
            self.redirect_timeout = redirect_timeout

        if waitroom_time_randomization_interval_s is not None:
            self.waitroom_time_randomization_interval_s = (
                waitroom_time_randomization_interval_s
            )

        if waitroom_timeout is not None:
            self.waitroom_timeout = waitroom_timeout

        if welcome_header_text is not None:
            self.welcome_header_text = welcome_header_text

        if game_header_text is not None:
            self.game_header_text = game_header_text

        if instructions is not None:
            self.instructions = instructions

        if welcome_text is not None:
            self.welcome_text = welcome_text

        if game_page_text is not None:
            self.game_page_text = game_page_text

        if final_page_text is not None:
            self.final_page_text = final_page_text

        if final_page_header_text is not None:
            self.final_page_header_text = final_page_header_text

        if page_title is not None:
            self.page_title = page_title

        if instructions_html_file is not None:
            self.instructions_html_file = instructions_html_file

        return self

    @property
    def simulate_waiting_room(self) -> bool:
        """
        Returns a boolean indicating whether or not we're
        forcing all participants to be in a waiting room, regardless
        of if they're waiting for other players or not.
        """
        return max(self.waitroom_time_randomization_interval_s) > 0

    def to_dict(self, serializable=False):
        config = copy.deepcopy(vars(self))
        if serializable:
            config = serialize_dict(config)
        return config


def serialize_dict(data):
    """
    Serialize a dictionary to JSON, removing unserializable keys recursively.

    :param data: Dictionary to serialize.
    :return: Serialized object with unserializable elements removed.
    """
    if isinstance(data, dict):
        # Use dictionary comprehension to process each key-value pair
        return {
            key: serialize_dict(value)
            for key, value in data.items()
            if is_json_serializable(value)
        }
    elif isinstance(data, list):
        # Use list comprehension to process each item
        return [
            serialize_dict(item) for item in data if is_json_serializable(item)
        ]
    elif is_json_serializable(data):
        return data
    else:
        return None  # or some other default value


def is_json_serializable(value):
    """
    Check if a value is JSON serializable.

    :param value: The value to check.
    :return: True if the value is JSON serializable, False otherwise.
    """
    try:
        json.dumps(value)
        return True
    except (TypeError, OverflowError):
        return False
