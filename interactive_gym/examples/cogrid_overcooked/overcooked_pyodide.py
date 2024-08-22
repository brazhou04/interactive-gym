from __future__ import annotations

import eventlet

eventlet.monkey_patch()

import argparse
from datetime import datetime

from cogrid.envs import registry

from interactive_gym.configurations import (
    configuration_constants,
    remote_config,
)
from interactive_gym.examples.cogrid_overcooked import (
    overcooked_callback,
    overcooked_utils,
)
from interactive_gym.server import server_app


MoveUp = 0
MoveDown = 1
MoveLeft = 2
MoveRight = 3
PickupDrop = 4
Toggle = 5
Noop = 6


POLICY_MAPPING = {
    0: configuration_constants.PolicyTypes.Human,
    1: "static/assets/overcooked/models/recurrent_ibc_0.onnx",
}


def env_creator(*args, **kwargs):
    """Generic function to return the Gymnasium environment"""
    return registry.make("Overcooked-RandomizedLayout-V0", render_mode=None)


# Map the actions to the arrow keys. The keys are Javascript key press events (all others ignored)
action_mapping = {
    "ArrowLeft": MoveLeft,
    "ArrowRight": MoveRight,
    "ArrowUp": MoveUp,
    "ArrowDown": MoveDown,
    "w": PickupDrop,
    "q": Toggle,
}

overcooked_env_initialization = None
with open(
    "interactive_gym/examples/cogrid_overcooked/pyodide_overcooked/environment_initialization.py"
) as f:
    overcooked_env_initialization = f.read()

config = (
    remote_config.RemoteConfig()
    .policies(
        policy_mapping=POLICY_MAPPING,
        frame_skip=5,
    )
    .environment(env_creator=env_creator, env_name="cogrid_overcooked")
    .rendering(
        fps=20,
        env_to_state_fn=overcooked_utils.overcooked_env_to_render_fn,
        assets_to_preload=overcooked_utils.overcooked_preload_assets_spec(),
        hud_text_fn=overcooked_utils.hud_text_fn,
        game_width=overcooked_utils.TILE_SIZE * 12,
        game_height=overcooked_utils.TILE_SIZE * 7,
        background="#e6b453",
    )
    .gameplay(
        default_action=Noop,
        action_mapping=action_mapping,
        num_episodes=20,
        input_mode=configuration_constants.InputModes.SingleKeystroke,
        callback=overcooked_callback.OvercookedCallback(),
    )
    .hosting(host="0.0.0.0", max_concurrent_games=100, max_ping=100)
    .user_experience(
        page_title="Overcooked",
        instructions_html_file="interactive_gym/server/static/templates/overcooked_instructions.html",
        welcome_header_text="Overcooked",
        game_header_text="Overcooked",
        game_page_html_fn=overcooked_utils.overcooked_game_page_header_fn,
        final_page_header_text="Overcooked",
        final_page_text="Thanks for playing, you will be redirected shortly...",
        end_game_redirect_url="https://cmu.ca1.qualtrics.com/jfe/form/SV_agZ3V7Uj4jfVweG",
        waitroom_timeout=5 * 60_000,  # 5 minutes in waitroom
        waitroom_timeout_redirect_url="https://cmu.ca1.qualtrics.com/jfe/form/SV_bIskl3fFOPC6ayy",
    )
    .pyodide(
        run_through_pyodide=True,
        environment_initialization_code=overcooked_env_initialization,
        packages_to_install=["numpy", "cogrid==0.0.3"],
    )
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=5701, help="Port number to listen on"
    )
    args = parser.parse_args()

    config.hosting(port=args.port)
    server_app.run(config)
