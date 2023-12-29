import gymnasium

import gymnasium as gym
import pygame
import math
from gymnasium.envs.classic_control import mountain_car
import numpy as np
from utils import object_contexts

ball_rotation = 0
prev_x = None


def mountaincar_to_render_state(env: gym.Env) -> list[dict]:
    global ball_rotation, prev_x, step
    y_offset = 0.05
    min_pos, max_pos = env.unwrapped.min_position, env.unwrapped.max_position
    env_ = env.unwrapped

    def _normalize_x(vals, minn=min_pos, maxx=max_pos):
        vals -= minn
        return vals / (maxx - minn)

    # Get coordinates of the car
    car_x = env_.state[0]
    if prev_x is None:
        prev_x = car_x

    car_y = 1 - env_._height(car_x) + y_offset
    car_x = _normalize_x(car_x)

    ball_rotation += (car_x - prev_x) * 2000
    prev_x = car_x

    car_sprite = object_contexts.Sprite(
        uuid="car", image_name="green_ball.png", x=car_x, y=car_y, angle=ball_rotation
    )

    # Get coordinates of the flag
    flagx = env_.goal_position
    flagy1 = 1 - env_._height(env_.goal_position)
    flagy2 = 0.05
    flagx = _normalize_x(flagx)
    flag_pole = object_contexts.Line(
        uuid="flag_line",
        color="#000000",
        points=[(flagx, flagy1), (flagx, flagy2)],
        width=3,
    )

    flag = object_contexts.Polygon(
        uuid="flag",
        color="#00FF00",
        points=[
            (flagx, flagy1),
            (flagx, flagy1 + 0.03),
            (flagx - 0.02, flagy1 + 0.015),
        ],
    )

    # Get line coordinates
    xs = np.linspace(min_pos, max_pos, 100)
    ys = 1 - env_._height(xs) + y_offset
    xs = _normalize_x(xs)
    xys = list(zip((xs), ys))
    line = object_contexts.Line(
        uuid="ground_line", color="#964B00", points=xys, width=1, fill_below=True
    )

    prop_done = int((env._elapsed_steps / env._max_episode_steps) * 100)
    time = object_contexts.Text(
        uuid="time_left", text=f"{prop_done}% complete", x=0.05, y=0.05, size=12,
    )

    return [
        car_sprite.as_dict(),
        line.as_dict(),
        flag_pole.as_dict(),
        flag.as_dict(),
        time.as_dict(),
    ]
