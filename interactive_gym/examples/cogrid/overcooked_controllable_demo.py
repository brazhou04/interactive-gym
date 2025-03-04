# from __future__ import annotations

import eventlet

eventlet.monkey_patch()

import argparse

from interactive_gym.server import app
from interactive_gym.scenes import scene
from interactive_gym.scenes import stager
from interactive_gym.examples.cogrid.pyodide_overcooked import (
    controllable_scenes,
    scenes,
)
from interactive_gym.scenes import static_scene

from interactive_gym.configurations import experiment_config


start_scene = (
    static_scene.StartScene()
    .scene(
        scene_id="overcooked_start_scene",
        experiment_config={},
        should_export_metadata=True,
    )
    .display(
        scene_header="Welcome",
        scene_body_filepath="interactive_gym/server/static/templates/overcooked_demo_instructions.html",
    )
)

end_scene = (
    static_scene.CompletionCodeScene()
    .scene(
        scene_id="end_completion_code_scene",
        should_export_metadata=True,
        experiment_config={},
    )
    .display(
        scene_header="Thank you for playing! If you have any questions, please contact us: chasemcd@andrew.cmu.edu.",
    )
)


control_scene = (
    static_scene.StaticScene()
    .scene("controls_static")
    .display(
        scene_header="Controls",
        scene_body_filepath="interactive_gym/server/static/templates/overcooked_controls_static.html",
    )
)


stager = stager.Stager(
    scenes=[
        start_scene,
        control_scene,
        # scenes.tutorial_gym_scene,
        # controllable_scenes.tutorial_with_bot_scene,
        controllable_scenes.control_tutorial_scene,
        # controllable_scenes.end_tutorial_static_scene,
        controllable_scenes.SCENES_BY_LAYOUT["cramped_room"],
        end_scene,
    ]
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--port", type=int, default=5702, help="Port number to listen on"
    )
    args = parser.parse_args()

    experiment_config = (
        experiment_config.ExperimentConfig()
        .experiment(
            stager=stager,
            experiment_id="overcooked_controllable",
            save_experiment_data=False,
        )
        .hosting(port=5704, host="0.0.0.0")
    )

    app.run(experiment_config)
