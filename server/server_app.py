import base64
import os
import queue
import random
import threading
import time
import uuid

import flask
import flask_socketio
from absl import logging

try:
    import cv2
except ImportError:
    cv2 = None
    logging.warn(
        "cv2 not installed. This is required if you're not "
        "defining a rendering function and want to (inefficiently) "
        "have the canvas display whatever is returned from `env.render()`."
    )

from server import remote_game
from configurations import remote_config
from server import utils

CONFIG = remote_config.RemoteConfig()

# Data structure to save subjects by their socket id
SUBJECTS = utils.ThreadSafeDict()

# Data structure to save subjects games in memory OBJECTS by their socket id
GAMES = utils.ThreadSafeDict()

# Games that are currently being played
ACTIVE_GAMES = utils.ThreadSafeSet()

# Queue of games IDs that are waiting for additional players to join. Note that some of these IDs might
# be stale (i.e. if FREE_MAP[id] = True)
WAITING_GAMES = []
WAITROOM_TIMEOUTS = utils.ThreadSafeDict()

# Mapping of users to locks associated with the ID. Enforces user-level serialization
USERS = utils.ThreadSafeDict()

# Mapping of user id's to the current game (room) they are in
USER_ROOMS = utils.ThreadSafeDict()

# Bitmap that indicates whether ID is currently in use. Game with ID=i is "freed" by setting FREE_MAP[i] = True
FREE_MAP = utils.ThreadSafeDict()

# Number of games allowed
NUM_EPISODES = 1

# Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
FREE_IDS = queue.Queue(maxsize=NUM_EPISODES)

# Initialize our ID tracking data
for i in range(NUM_EPISODES):
    FREE_IDS.put(i)
    FREE_MAP[i] = True


#######################
# Flask Configuration #
#######################

app = flask.Flask(__name__, template_folder=os.path.join("static", "templates"))
app.config["SECRET_KEY"] = "secret!"

app.config["DEBUG"] = os.getenv("FLASK_ENV", "production") == "development"
socketio = flask_socketio.SocketIO(
    app, cors_allowed_origins="*", logger=app.config["DEBUG"]
)


def try_create_game() -> tuple[
    remote_game.RemoteGame | None, None | RuntimeError | Exception
]:
    try:
        game_id = FREE_IDS.get(block=False)
        assert FREE_MAP[game_id], "Game ID already in use!"
        game = remote_game.RemoteGame(config=CONFIG, game_id=game_id)
    except queue.Empty:
        err = RuntimeError("Server at maximum capacity.")
        return None, err
    except Exception as e:
        return None, e
    else:
        GAMES[game_id] = game
        FREE_MAP[game_id] = False
        return game, None


def _create_game() -> None:
    """
    Create a new game and add it to WAITING_GAMES and start the lobby timer.
    If creation fails, we emit the create_game_failed event.
    """
    game, err = try_create_game()
    if game is None:
        socketio.emit("create_game_failed", {"error": err.__repr__()})
        return

    WAITING_GAMES.append(game.game_id)
    WAITROOM_TIMEOUTS[game.game_id] = time.time() + (
        CONFIG.waitroom_timeout / 1000
    )  # convert waitroom timeout to seconds


@socketio.on("join")
def join_or_create_game(data):
    subject_id = flask.request.sid

    with SUBJECTS[subject_id]:

        # already in a game so don't join a new one
        if _get_existing_game(subject_id) is not None:
            return

        game = _create_or_join_game()

        with game.lock:
            flask_socketio.join_room(game.game_id)
            USER_ROOMS[subject_id] = game.game_id

            # TODO(chase): Figure out how to specify the ID in the URL for debugging
            available_human_player_ids = game.get_available_human_player_ids()
            game.add_player(random.choice(available_human_player_ids), subject_id)

            if game.is_ready_to_start():
                WAITING_GAMES.remove(game.game_id)
                ACTIVE_GAMES.add(game.game_id)
                socketio.emit(
                    "start_game",
                    {"config": CONFIG.to_dict(serializable=True)},
                    room=game.game_id,
                )
                socketio.start_background_task(run_game, game)
            else:
                remaining_wait_time = (
                    WAITROOM_TIMEOUTS[game.game_id] - time.time()
                ) * 1000  # convert seconds to ms
                socketio.emit(
                    "waiting_room",
                    {
                        "cur_num_players": game.cur_num_human_players(),
                        "players_needed": len(game.get_available_human_player_ids()),
                        "ms_remaining": remaining_wait_time,
                    },
                    room=game.game_id,
                )


def _get_existing_game(subject_id) -> remote_game.RemoteGame | None:
    """check if there's an existing game for this subject"""
    game = GAMES.get(USER_ROOMS.get(subject_id, None), None)
    return game


def _create_or_join_game() -> remote_game.RemoteGame:
    """
    This function will either
        - get a game that is waiting for players
        - create and return a new game
    """

    # Look for games that are waiting for more players
    game = get_waiting_game()
    if game is not None:
        return game

    # Lastly, we'll make a new game and retrieve that
    _create_game()  # adds to waiting game
    game = get_waiting_game()

    assert game is not None, "Game retrieval failed!"

    return game


def get_waiting_game() -> None | remote_game.RemoteGame:
    if WAITING_GAMES:
        return GAMES.get(WAITING_GAMES[0], None)

    return None


def _cleanup_game(game: remote_game.RemoteGame):
    if FREE_MAP[game.game_id]:
        raise ValueError("Freeing a free game!")

    for subject_id in game.human_players.values():
        if subject_id is utils.Available:
            continue
        del USER_ROOMS[subject_id]

    socketio.close_room(game.game_id)

    FREE_MAP[game.game_id] = True
    FREE_IDS.put(game.game_id)

    if game.game_id in ACTIVE_GAMES:
        ACTIVE_GAMES.remove(game.game_id)

    del GAMES[game.game_id]


def _leave_game(subject_id) -> bool:
    """Removes the subject with `subject_id` from any current game."""
    game = _get_existing_game(subject_id)

    if game is None:
        return False

    with game.lock:
        flask_socketio.leave_room(game.game_id)
        del USER_ROOMS[subject_id]
        game.remove_human_player(subject_id)

        game_was_active = game.game_id in ACTIVE_GAMES
        game_is_empty = game.cur_num_human_players() == 0
        if game_was_active and game_is_empty:
            game.tear_down()
        elif game_is_empty:
            _cleanup_game(game)
        elif not game_was_active:
            remaining_wait_time = (WAITROOM_TIMEOUTS[game.game_id] - time.time()) * 1000
            socketio.emit(
                "waiting_room",
                {
                    "cur_num_players": game.cur_num_human_players(),
                    "players_needed": len(game.get_available_human_player_ids()),
                    "ms_remaining": remaining_wait_time,  # convert to ms remaining
                },
                room=game.game_id,
            )
        elif game_was_active and game.is_ready_to_start():
            pass
        elif game_was_active and not game_is_empty:
            game.tear_down()

    return game_was_active


@app.route("/")
def index(*args):
    """If no subject ID provided, generate a UUID and re-route them."""
    subject_name = str(uuid.uuid4())
    return flask.redirect(flask.url_for("user_index", subject_name=subject_name))


@app.route("/instructions")
def instructions():
    """Display instructions page."""
    return flask.render_template("instructions.html", async_mode=socketio.async_mode,)


@app.route("/<subject_name>")
def user_index(subject_name):
    return flask.render_template(
        "index.html",
        async_mode=socketio.async_mode,
        welcome_header_text=CONFIG.welcome_header_text,
        welcome_text=CONFIG.welcome_text,
        game_header_text=CONFIG.game_header_text,
        game_page_text=CONFIG.game_page_text,
        final_page_header_text=CONFIG.final_page_header_text,
        final_page_text=CONFIG.final_page_text,
    )


@socketio.on("connect")
def on_connect():
    subject_socket_id = flask.request.sid

    if subject_socket_id in SUBJECTS:
        return

    SUBJECTS[subject_socket_id] = threading.Lock()


@socketio.on("leave_game")
def on_leave(data):
    subject_id = flask.request.sid
    with SUBJECTS[subject_id]:
        game_was_active = _leave_game(subject_id)

        if game_was_active:
            socketio.emit(
                "end_game", {},
            )
        else:
            socketio.emit("end_lobby")


@socketio.on("disconnect")
def on_disconnect():
    subject_id = flask.request.sid

    if subject_id not in SUBJECTS:
        return

    with SUBJECTS[subject_id]:
        _leave_game(subject_id)

    del SUBJECTS[subject_id]


@socketio.on("send_pressed_keys")
def on_action(data):
    """
    Translate pressed keys into game action and add them to the pending_actions queue.

    TODO(chase): Check for composite actions, multiple keys, etc.
    """
    subject_id = flask.request.sid
    game = _get_existing_game(subject_id)

    pressed_keys = data["pressed_keys"]

    if not game or not any([k in CONFIG.action_mapping for k in pressed_keys]):
        return

    action = None
    for k in pressed_keys:
        if k in CONFIG.action_mapping:
            action = k
            break
    assert action is not None

    game.enqueue_action(subject_id, CONFIG.action_mapping[action])


def run_game(game: remote_game.RemoteGame):
    end_status = [remote_game.GameStatus.Inactive, remote_game.GameStatus.Done]
    game.reset()
    while game.status not in end_status:
        socketio.emit("request_pressed_keys", {})
        with game.lock:
            game.tick()

        render_game(game)
        if game.status == remote_game.GameStatus.Reset:
            socketio.emit(
                "game_reset",
                {
                    "timeout": CONFIG.reset_timeout,
                    "config": CONFIG.to_dict(serializable=True),
                },
                room=game.game_id,
            )
            socketio.sleep(CONFIG.reset_timeout / 1000)
            game.reset()

        socketio.sleep(1 / game.config.fps)

    with game.lock:
        socketio.emit(
            "end_game",
            {"redirect_url": CONFIG.redirect_url, "timeout": CONFIG.redirect_timeout},
            room=game.game_id,
        )

        if game.status != remote_game.GameStatus.Inactive:
            game.tear_down()

        _cleanup_game(game)


def render_game(game: remote_game.RemoteGame):
    state = None
    encoded_image = None
    if CONFIG.env_to_state_fn is not None:
        # generate a state object representation
        state = CONFIG.env_to_state_fn(game.env)
    else:
        # Generate a base64 image of the game and send it to display
        assert cv2 is not None, "Must install cv2 to use default image rendering!"
        game_image = game.env.render()
        _, encoded_image = cv2.imencode(".png", game_image)
        encoded_image = base64.b64encode(encoded_image).decode()

    # TODO(chase): this emits the same state to every player in a room, but we may want
    #   to have different observations for each player. Figure that out (maybe state is a dict
    #   with player_ids and their respective observations?).
    socketio.emit(
        "environment_state",
        {"state": state, "game_image_base64": encoded_image, "step": game.tick_num,},
        room=game.game_id,
    )


def run(config):
    global CONFIG, NUM_EPISODES, FREE_IDS, FREE_MAP
    CONFIG = config

    # handler = logging.lo(CONFIG.logfile)
    # handler.setLevel(logging.ERROR)
    # app.logger.addHandler(handler)

    # Number of games allowed
    NUM_EPISODES = CONFIG.num_episodes

    # Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
    FREE_IDS = queue.Queue(maxsize=NUM_EPISODES)

    # Initialize our ID tracking data
    for i in range(NUM_EPISODES):
        FREE_IDS.put(i)
        FREE_MAP[i] = True

    socketio.run(
        app,
        log_output=app.config["DEBUG"],
        port=CONFIG.port,
        host=CONFIG.host,
        allow_unsafe_werkzeug=True,
    )
