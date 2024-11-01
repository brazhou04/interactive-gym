from __future__ import annotations

import eventlet
import copy

eventlet.monkey_patch()


from interactive_gym.configurations import (
    configuration_constants,
)
from interactive_gym.examples.cogrid import (
    overcooked_utils,
)
from interactive_gym.scenes import gym_scene
from interactive_gym.scenes import static_scene
from interactive_gym.scenes import scene


SCENES_PER_SETTING = 3


# Constants for controls/actions/etc.
MoveUp = 0
MoveDown = 1
MoveLeft = 2
MoveRight = 3
PickupDrop = 4
Toggle = 5
Noop = 6

# Map the actions to the arrow keys. The keys are Javascript key press events (all others ignored)
action_mapping = {
    "ArrowLeft": MoveLeft,
    "ArrowRight": MoveRight,
    "ArrowUp": MoveUp,
    "ArrowDown": MoveDown,
    "w": PickupDrop,
    "W": PickupDrop,
    "q": Toggle,
    "Q": Toggle,
}

IBC_POLICY_MAPPING_CRAMPED_ROOM = {
    0: configuration_constants.PolicyTypes.Human,
    1: "static/assets/overcooked/models/ibc_cramped_room_00.onnx",
}

# Define the start scene, which is the landing page for participants.
start_scene = (
    static_scene.StartScene()
    .scene(
        scene_id="overcooked_start_scene",
        experiment_config={},
        should_export_metadata=True,
    )
    .display(
        scene_header="Welcome",
        scene_body_filepath="interactive_gym/server/static/templates/overcooked_controllable_instructions.html",
    )
)


on_game_step_code = """
import js
interactive_gym_globals = dict(js.window.interactiveGymGlobals.object_entries())
env.reward_weights[1] = {k: interactive_gym_globals.get(k, 0.0) for k in env.reward_weights[1].keys()}
"""
control_tutorial_scene = (
    gym_scene.GymScene()
    .scene(scene_id="cramped_room_control_tutorial_0", experiment_config={})
    .policies(
        policy_mapping={
            0: "static/assets/overcooked/models/ibc_cramped_room_00.onnx",
            1: "static/assets/overcooked/models/ibc_cramped_room_00.onnx",
        },
        frame_skip=5,
    )
    .rendering(
        fps=30,
        assets_to_preload=overcooked_utils.overcooked_preload_assets_spec(),
        hud_text_fn=overcooked_utils.hud_text_fn,
        game_width=overcooked_utils.TILE_SIZE * 7,
        game_height=overcooked_utils.TILE_SIZE * 6,
        background="#e6b453",
    )
    .gameplay(
        default_action=Noop,
        action_mapping=action_mapping,
        num_episodes=1,
        max_steps=2000,
        input_mode=configuration_constants.InputModes.SingleKeystroke,
    )
    .user_experience(
        scene_header="Overcooked",
        scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/control_tutorial.html",
        game_page_html_fn=overcooked_utils.overcooked_game_page_header_fn,
        in_game_scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/control_tutorial_in_game_body.html",
    )
    .pyodide(
        run_through_pyodide=True,
        environment_initialization_code_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/env_initialization/cramped_room_controllable_tutorial_environment_initialization.py",
        on_game_step_code=on_game_step_code,
        packages_to_install=["numpy", "cogrid==0.0.9", "opencv-python"],
    )
)


tutorial_with_bot_scene = (
    gym_scene.GymScene()
    .scene(scene_id="cramped_room_with_bot_tutorial_0", experiment_config={})
    .policies(policy_mapping=IBC_POLICY_MAPPING_CRAMPED_ROOM, frame_skip=5)
    .rendering(
        fps=30,
        env_to_state_fn=overcooked_utils.overcooked_env_to_render_fn,
        assets_to_preload=overcooked_utils.overcooked_preload_assets_spec(),
        hud_text_fn=overcooked_utils.hud_text_fn,
        game_width=overcooked_utils.TILE_SIZE * 7,
        game_height=overcooked_utils.TILE_SIZE * 6,
        background="#e6b453",
    )
    .gameplay(
        default_action=Noop,
        action_mapping=action_mapping,
        num_episodes=1,
        max_steps=1350,
        input_mode=configuration_constants.InputModes.SingleKeystroke,
    )
    .user_experience(
        scene_header="Overcooked",
        scene_body="""
        <center><p>
        You'll now try playing with a partner for a single practice round. 
        <br><br> 
        "You will be playing on the layout pictured below. "
        '<center><img src="static/assets/overcooked/cramped_room.png" alt="Annotated Overcooked environment." height="270" width="315"></center>'
        
        <div style="display: flex; justify-content: center; align-items: center; gap: 40px; margin: 20px 0;">
        <div style="text-align: center;">
            <img src="static/assets/overcooked/blue_chef.png" alt="Chef with blue hat." width="24" height="32">
            <p style="margin: 5px 0;">Your Chef</p>
        </div>
        <div style="text-align: center;">
            <img src="static/assets/overcooked/green_chef.png" alt="Chef with green hat." width="24" height="32">
            <p style="margin: 5px 0;">AI Chef</p>
        </div>
    </div>
        
        When the button activates, click it to begin. 
        </p></center>
        """,
        game_page_html_fn=overcooked_utils.overcooked_game_page_header_fn,
        in_game_scene_body="""
        <center>
        <p>
        Use the arrow keys <img src="static/assets/keys/arrow_keys_2.png" alt="Keyboard arrow keys" height="24" width="20" style="vertical-align:middle;"> 
        to control your chef <img src="static/assets/overcooked/blue_chef.png" alt="Blue Chef" height="24" width="24" style="vertical-align:middle;"> 
        and press <img src="static/assets/keys/icons8-w-key-50.png" alt="W key" height="24" width="24" style="vertical-align:middle;"> to pick up and 
        drop objects. Try to deliver as many dishes as possible by combining onions in the pot, plating the cooked onions, 
        and delivering them to the grey delivery zone.
        </p>
        </center>
        <br><br>
        """,
    )
    .pyodide(
        run_through_pyodide=True,
        environment_initialization_code_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/env_initialization/cramped_room_environment_initialization.py",
        packages_to_install=["numpy", "cogrid==0.0.9", "opencv-python"],
    )
)


end_tutorial_static_scene = (
    static_scene.StaticScene()
    .scene(scene_id="end_tutorial_static_scene", experiment_config={})
    .display(
        scene_header="Tutorial Complete",
        scene_body="You've completed the tutorial! All rounds after this will be part of the main study and all points earned will count towards your bonus.",
    )
)


cramped_room_controllable_ = (
    gym_scene.GymScene()
    .scene(scene_id="cramped_room_controllable", experiment_config={})
    .policies(policy_mapping=IBC_POLICY_MAPPING_CRAMPED_ROOM, frame_skip=5)
    .rendering(
        fps=30,
        assets_to_preload=overcooked_utils.overcooked_preload_assets_spec(),
        hud_text_fn=overcooked_utils.hud_text_fn,
        game_width=overcooked_utils.TILE_SIZE * 7,
        game_height=overcooked_utils.TILE_SIZE * 6,
        background="#e6b453",
    )
    .gameplay(
        default_action=Noop,
        action_mapping=action_mapping,
        num_episodes=1,
        max_steps=1350,
        input_mode=configuration_constants.InputModes.SingleKeystroke,
    )
    .user_experience(
        scene_header="Overcooked",
        scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/controllable_cramped_room.html",
        game_page_html_fn=overcooked_utils.overcooked_game_page_header_fn,
        in_game_scene_body="""
        <center>
        <p>
        Use the arrow keys <img src="static/assets/keys/arrow_keys_2.png" alt="Keyboard arrow keys" height="24" width="20" style="vertical-align:middle;"> 
        to control your chef <img src="static/assets/overcooked/blue_chef.png" alt="Blue Chef" height="24" width="24" style="vertical-align:middle;"> 
        and press <img src="static/assets/keys/icons8-w-key-50.png" alt="W key" height="24" width="24" style="vertical-align:middle;"> to pick up and 
        drop objects. Try to deliver as many dishes as possible by combining onions in the pot, plating the cooked onions, 
        and delivering them to the grey delivery zone.
        </p>
        <div style="border: 1px solid black; padding: 10px; display: inline-block;">
            <p style="margin: 0 0 5px 0; font-weight: bold;">Current AI Partner Behavior Settings</p>
            <p id="reward-status" style="margin: 0;"></p>
        </div>
        <script>
            function getControlText(value) {
                if (value === -1) return "<span style='color: red'>Discourage</span>";
                if (value === 1) return "<span style='color: green'>Encourage</span>"; 
                if (value === 0) return "<span style='color: #b3a600'>Neutral</span>";
                return value;
            }


            document.getElementById('reward-status').innerHTML = 
                "Delivering Dishes: " + getControlText(window.interactiveGymGlobals.delivery_act_reward) + ", " +
                "Onions in Pot: " + getControlText(window.interactiveGymGlobals.onion_in_pot_reward);
        </script>
        </center>
        """,
    )
    .pyodide(
        run_through_pyodide=True,
        environment_initialization_code_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/env_initialization/cramped_room_controllable_environment_initialization.py",
        packages_to_install=["numpy", "cogrid==0.0.9", "opencv-python"],
    )
)
cramped_room_controllable_eval_ = (
    static_scene.ScalesAndTextBox(
        scale_questions=[
            "My partner followed its behavior settings.",
            "My partner's behavior was predictable.",
            "My partner was effective as a teammate.",
            "My partner perceived accurately what tasks I was trying to accomplish.",
            "My partner felt human-like.",
            "My ability to control my partner's behavior made it more effective as a teammate.",
            "My ability to control my partner's behavior made it more predictable.",
        ],
        # scale_labels=["Not at all", "Very much"],
        pre_scale_header="Please indicate the extent to which you agree with the following statements about your partner in the previous round.",
        text_box_header="Please describe any additional reasoning for your selections. This might include specific actions or behaviors. You may write N/A if you do not have any anything to add.",
    )
    .scene(scene_id="cramped_room_controllable_eval_", experiment_config={})
    .display(scene_subheader="Feedback About Your AI Partner")
)


cramped_room_controllable_scenes = [
    scene.SceneWrapper(
        [
            copy.deepcopy(cramped_room_controllable_).scene(
                scene_id=f"cramped_room_controllable_{i}", experiment_config={}
            ),
            copy.deepcopy(cramped_room_controllable_eval_).scene(
                scene_id=f"cramped_room_controllable_eval_{i}",
                experiment_config={},
            ),
        ]
    )
    for i in range(SCENES_PER_SETTING)
]


cramped_room_fixed_ = (
    copy.deepcopy(cramped_room_controllable_)
    .scene(scene_id="cramped_room_fixed_", experiment_config={})
    .policies(policy_mapping=IBC_POLICY_MAPPING_CRAMPED_ROOM, frame_skip=5)
    .user_experience(
        scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/fixed_cramped_room.html",
    )
)
cramped_room_fixed_eval_ = (
    static_scene.ScalesAndTextBox(
        scale_questions=[
            "My partner followed its behavior settings.",
            "My partner's behavior was predictable.",
            "My partner was effective as a teammate.",
            "My partner perceived accurately what tasks I was trying to accomplish.",
            "My partner felt human-like.",
            "My inability to control my partner's behavior made it less effective as a teammate.",
            "My inability to control my partner's behavior made it less predictable.",
        ],
        pre_scale_header="Please indicate the extent to which you agree with the following statements about your partner in the previous round.",
        text_box_header="Please describe any additional reasoning for your selections. This might include specific actions or behaviors. You may write N/A if you do not have any anything to add.",
    )
    .scene(scene_id="cramped_room_fixed_eval_", experiment_config={})
    .display(scene_subheader="Feedback About Your AI Partner")
)

cramped_room_fixed_scenes = [
    scene.SceneWrapper(
        [
            copy.deepcopy(cramped_room_fixed_).scene(
                scene_id=f"cramped_room_fixed_{i}", experiment_config={}
            ),
            copy.deepcopy(cramped_room_fixed_eval_).scene(
                scene_id=f"cramped_room_fixed_eval_{i}", experiment_config={}
            ),
        ]
    )
    for i in range(SCENES_PER_SETTING)
]


cramped_room_nospec_ = (
    gym_scene.GymScene()
    .scene(scene_id="cramped_room_nospec", experiment_config={})
    .policies(policy_mapping=IBC_POLICY_MAPPING_CRAMPED_ROOM, frame_skip=5)
    .rendering(
        fps=30,
        assets_to_preload=overcooked_utils.overcooked_preload_assets_spec(),
        hud_text_fn=overcooked_utils.hud_text_fn,
        game_width=overcooked_utils.TILE_SIZE * 7,
        game_height=overcooked_utils.TILE_SIZE * 6,
        background="#e6b453",
    )
    .gameplay(
        default_action=Noop,
        action_mapping=action_mapping,
        num_episodes=1,
        max_steps=1350,
        input_mode=configuration_constants.InputModes.SingleKeystroke,
    )
    .user_experience(
        scene_header="Overcooked",
        scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/nospec_cramped_room.html",
        game_page_html_fn=overcooked_utils.overcooked_game_page_header_fn,
        in_game_scene_body="""
        <center>
        <p>
        Use the arrow keys <img src="static/assets/keys/arrow_keys_2.png" alt="Keyboard arrow keys" height="24" width="20" style="vertical-align:middle;"> 
        to control your chef <img src="static/assets/overcooked/blue_chef.png" alt="Blue Chef" height="24" width="24" style="vertical-align:middle;"> 
        and press <img src="static/assets/keys/icons8-w-key-50.png" alt="W key" height="24" width="24" style="vertical-align:middle;"> to pick up and 
        drop objects. Try to deliver as many dishes as possible by combining onions in the pot, plating the cooked onions, 
        and delivering them to the grey delivery zone.
        </p>
        </center>
        """,
    )
    .pyodide(
        run_through_pyodide=True,
        environment_initialization_code_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/env_initialization/cramped_room_controllable_environment_initialization.py",
        packages_to_install=["numpy", "cogrid==0.0.9", "opencv-python"],
    )
)
cramped_room_nospec_eval_ = (
    static_scene.ScalesAndTextBox(
        scale_questions=[
            "My partner's behavior was predictable.",
            "My partner was effective as a teammate.",
            "My partner perceived accurately what tasks I was trying to accomplish.",
            "My partner felt human-like.",
            "My inability to control my partner's behavior made it less effective as a teammate.",
            "My inability to control my partner's behavior made it less predictable.",
        ],
        # scale_labels=["Not at all", "Very much"],
        pre_scale_header="Please indicate the extent to which you agree with the following statements about your partner in the previous round.",
        text_box_header="Please describe any additional reasoning for your selections. This might include specific actions or behaviors. You may write N/A if you do not have any anything to add.",
    )
    .scene(scene_id="cramped_room_nospec_eval_", experiment_config={})
    .display(scene_subheader="Feedback About Your AI Partner")
)

cramped_room_nospec_scenes = [
    scene.SceneWrapper(
        [
            copy.deepcopy(cramped_room_nospec_).scene(
                scene_id=f"cramped_room_nospec_{i}", experiment_config={}
            ),
            copy.deepcopy(cramped_room_nospec_eval_).scene(
                scene_id=f"cramped_room_nospec_eval_{i}", experiment_config={}
            ),
        ]
    )
    for i in range(SCENES_PER_SETTING)
]


cramped_room_randomization = scene.RandomizeOrder(
    [
        *cramped_room_controllable_scenes,
        *cramped_room_fixed_scenes,
        *cramped_room_nospec_scenes,
    ],
)

choice_cramped_room_ = (
    copy.deepcopy(cramped_room_controllable_)
    .scene(scene_id="cramped_room_choice_0", experiment_config={})
    .policies(policy_mapping=IBC_POLICY_MAPPING_CRAMPED_ROOM, frame_skip=5)
    .user_experience(
        scene_body_filepath="interactive_gym/examples/cogrid/pyodide_overcooked/choice_cramped_room.html",
        in_game_scene_body="""
        <center>
        <p>
        Use the arrow keys <img src="static/assets/keys/arrow_keys_2.png" alt="Keyboard arrow keys" height="24" width="20" style="vertical-align:middle;"> 
        to control your chef <img src="static/assets/overcooked/blue_chef.png" alt="Blue Chef" height="24" width="24" style="vertical-align:middle;"> 
        and press <img src="static/assets/keys/icons8-w-key-50.png" alt="W key" height="24" width="24" style="vertical-align:middle;"> to pick up and 
        drop objects. Try to deliver as many dishes as possible by combining onions in the pot, plating the cooked onions, 
        and delivering them to the grey delivery zone.
        </p>
        <div id="behavior-settings" style="border: 1px solid black; padding: 10px; display: inline-block;">
            <p style="margin: 0 0 5px 0; font-weight: bold;">Current AI Partner Behavior Settings</p>
            <p id="reward-status" style="margin: 0;"></p>
        </div>
        <script>
            function getControlText(value) {
                if (value === -1) return "<span style='color: red'>Discourage</span>";
                if (value === 1) return "<span style='color: green'>Encourage</span>"; 
                if (value === 0) return "<span style='color: #b3a600'>Neutral</span>";
                return value;
            }

            if (window.interactiveGymGlobals.partner_mode === "noSpec") {
                document.getElementById('behavior-settings').style.display = 'none';
            } else {
                document.getElementById('reward-status').innerHTML = 
                    "Delivering Dishes: " + getControlText(window.interactiveGymGlobals.delivery_act_reward) + ", " +
                    "Onions in Pot: " + getControlText(window.interactiveGymGlobals.onion_in_pot_reward);
            }
        </script>
        </center>
        """,
    )
)


cramped_room_scenes = scene.SceneWrapper(
    [cramped_room_randomization, choice_cramped_room_]
)

# class ScoreCompletionCodeScene(static_scene.CompletionCodeScene):
#     def _create_html_completion_code(self) -> str:
#         """Create HTML content for displaying a completion code.

#         This method generates a unique completion code using UUIDs and formats it as HTML.
#         It also includes instructions for participants to copy and submit the code.

#         :return: A tuple containing the HTML content and the completion code
#         :rtype: tuple[str, str]
#         """
#         html, completion_code = super()._create_html_completion_code()

#         score_html = """
#         <script>
#             var dishesDelivered = window.interactiveGymGlobals.dishesDelivered || 0;
#             document.write(`
#                 <div style="margin: 20px 0;">
#                     <p>You delivered a total of <strong>${dishesDelivered}</strong> dishes during the stud.</p>
#                 </div>
#             `);
#         </script>
#         """
#         html = score_html + html


#         return html, completion_code


# score_completion_code_scene = (
#     static_scene.CompletionCodeScene()
#     .scene(
#         scene_id="end_completion_code_scene",
#         should_export_metadata=True,
#         experiment_config={},
#     )
#     .display(
#         scene_header="Thank you for participating!",
#     )
# )


end_scene = (
    static_scene.CompletionCodeScene()
    .scene(
        scene_id="end_completion_code_scene",
        should_export_metadata=True,
        experiment_config={},
    )
    .display(
        scene_header="Thank you for participating!",
    )
)
