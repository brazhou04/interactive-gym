import base64
import os
import queue
import random
import threading
import time
import uuid
import itertools
import atexit
import secrets


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
from configurations import configuration_constants
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
MAX_CONCURRENT_GAMES = 1

# Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
FREE_IDS = queue.Queue(maxsize=MAX_CONCURRENT_GAMES)

# holds reset events so we only continue in game loop when triggered
RESET_EVENTS = utils.ThreadSafeDict()

# Initialize our ID tracking data
for i in range(MAX_CONCURRENT_GAMES):
    FREE_IDS.put(i)
    FREE_MAP[i] = True
    RESET_EVENTS[i] = utils.ThreadSafeDict()

# Generate a unique identifier for the server session
SERVER_SESSION_ID = secrets.token_urlsafe(16)

#######################
# Flask Configuration #
#######################

app = flask.Flask(__name__, template_folder=os.path.join("static", "templates"))
app.config["SECRET_KEY"] = "secret!"

app.config["DEBUG"] = os.getenv("FLASK_ENV", "production") == "development"
socketio = flask_socketio.SocketIO(
    app, cors_allowed_origins="*", logger=app.config["DEBUG"]
)


def try_create_game() -> (
    tuple[remote_game.RemoteGame | None, None | RuntimeError | Exception]
):
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
        socketio.emit(
            "create_game_failed", {"error": err.__repr__()}, room=flask.request.sid
        )
        return

    WAITING_GAMES.append(game.game_id)
    WAITROOM_TIMEOUTS[game.game_id] = time.time() + (
        CONFIG.waitroom_timeout / 1000
    )  # convert waitroom timeout to seconds


@socketio.on("join")
def join_or_create_game(data):
    subject_id = flask.request.sid
    client_session_id = data.get("session_id")

    # Validate session
    if not is_valid_session(client_session_id):
        flask_socketio.emit(
            "invalid_session",
            {"message": "Session is invalid. Please reconnect."},
            room=subject_id,
        )
        return

    with SUBJECTS[subject_id]:
        # already in a game so don't join a new one
        if _get_existing_game(subject_id) is not None:
            return

        game = _create_or_join_game()
        if game is None:  # there was an error that is now displayed
            return

        with game.lock:
            print(f"Subject {subject_id} joining room {game.game_id}")
            flask_socketio.join_room(game.game_id)
            USER_ROOMS[subject_id] = game.game_id

            # add unique event to sync resets across players
            RESET_EVENTS[game.game_id][subject_id] = threading.Event()

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
                    room=subject_id,
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

    # assert game is not None, "Game retrieval failed!"

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
        del RESET_EVENTS[game.game_id][subject_id]

    socketio.close_room(game.game_id)

    FREE_MAP[game.game_id] = True
    FREE_IDS.put(game.game_id)
    del GAMES[game.game_id]

    if game.game_id in ACTIVE_GAMES:
        ACTIVE_GAMES.remove(game.game_id)


def _leave_game(subject_id) -> bool:
    """Removes the subject with `subject_id` from any current game."""
    game = _get_existing_game(subject_id)

    if game is None:
        return False

    with game.lock:

        flask_socketio.leave_room(game.game_id)
        del USER_ROOMS[subject_id]
        del RESET_EVENTS[game.game_id][subject_id]
        game.remove_human_player(subject_id)

        game_was_active = game.game_id in ACTIVE_GAMES
        game_is_empty = game.cur_num_human_players() == 0

        # If the game was running but there are no other players,
        # we can cleanly end it.
        if game_was_active and game_is_empty:
            exit_status = utils.GameExitStatus.ActiveNoPlayers
            game.tear_down()

        # If the game wasn't active and there are no players,
        # cleanup the traces of the game.
        elif game_is_empty:
            exit_status = utils.GameExitStatus.InactiveNoPlayers
            _cleanup_game(game)

        # if the game was not active and not empty, redirect the players back to the waitroom.
        elif not game_was_active:
            exit_status = utils.GameExitStatus.InactiveWithOtherPlayers
            remaining_wait_time = (WAITROOM_TIMEOUTS[game.game_id] - time.time()) * 1000
            # TODO(chase): check if we need this?
            socketio.emit(
                "waiting_room",
                {
                    "cur_num_players": game.cur_num_human_players(),
                    "players_needed": len(game.get_available_human_player_ids()),
                    "ms_remaining": remaining_wait_time,  # convert to ms remaining
                },
                room=game.game_id,
            )
        # elif game_was_active and game.is_ready_to_start():
        #     raise ValueError("This shouldn't happen without spectators.")
        elif game_was_active and not game_is_empty:
            print("plyyer exited with other players active")
            exit_status = utils.GameExitStatus.ActiveWithOtherPlayers
            game.tear_down()
        else:
            raise NotImplementedError("Something went wrong on exit!")

    return exit_status


@app.route("/")
def index(*args):
    """If no subject ID provided, generate a UUID and re-route them."""
    subject_name = str(uuid.uuid4())
    return flask.redirect(flask.url_for("user_index", subject_name=subject_name))


@app.route("/<subject_name>")
def user_index(subject_name):

    instructions_html = ""
    if CONFIG.instructions_html_file is not None:
        import os

        try:
            with open(CONFIG.instructions_html_file, "r", encoding="utf-8") as f:
                instructions_html = f.read()
        except FileNotFoundError:
            instructions_html = f"<p> Unable to load instructions file {CONFIG.instructions_html_file}.</p>"

    return flask.render_template(
        "index.html",
        async_mode=socketio.async_mode,
        welcome_header_text=CONFIG.welcome_header_text,
        welcome_text=CONFIG.welcome_text,
        indstructions_html=instructions_html,
        game_header_text=CONFIG.game_header_text,
        game_page_text=CONFIG.game_page_text,
        final_page_header_text=CONFIG.final_page_header_text,
        final_page_text=CONFIG.final_page_text,
    )


def is_valid_session(client_session_id):
    return client_session_id == SERVER_SESSION_ID


@socketio.on("connect")
def on_connect():
    subject_socket_id = flask.request.sid

    if subject_socket_id in SUBJECTS:
        return

    SUBJECTS[subject_socket_id] = threading.Lock()

    # Send the current server session ID to the client
    flask_socketio.emit(
        "server_session_id", {"session_id": SERVER_SESSION_ID}, room=subject_socket_id
    )


@socketio.on("leave_game")
def on_leave(data):
    subject_id = flask.request.sid
    client_session_id = data.get("session_id")

    # Validate session
    if not is_valid_session(client_session_id):
        flask_socketio.emit(
            "invalid_session",
            {"message": "Session is invalid. Please refresh the page."},
            room=subject_id,
        )
        return

    with SUBJECTS[subject_id]:
        game = _get_existing_game(subject_id=subject_id)
        if game is not None:
            game_id = game.game_id
        else:
            game_id = None

        # game_was_active = _leave_game(subject_id)

        game_exit_status = _leave_game(subject_id)
        if game_exit_status in [
            utils.GameExitStatus.ActiveNoPlayers,
            utils.GameExitStatus.ActiveWithOtherPlayers,
        ]:
            print(
                f"Ending game bc subject {subject_id} left room {game_id}; Exit Status: {game_exit_status}"
            )
            socketio.emit(
                "end_game",
                {},
                room=game_id,
            )
        else:
            socketio.emit("end_lobby", room=game_id)


@socketio.on("disconnect")
def on_disconnect():
    subject_id = flask.request.sid
    game = _get_existing_game(subject_id)
    print(
        "Subject",
        subject_id,
        "disconnected, Game ID:",
        game.game_id if game is not None else "No existing game.",
    )

    if subject_id not in SUBJECTS:
        return

    with SUBJECTS[subject_id]:
        _leave_game(subject_id)

    del SUBJECTS[subject_id]


@socketio.on("send_pressed_keys")
def on_action(data):
    """
    Translate pressed keys into game action and add them to the pending_actions queue.
    """
    subject_id = flask.request.sid
    client_session_id = data.get("session_id")

    # Validate session
    if not is_valid_session(client_session_id):
        flask_socketio.emit(
            "invalid_session",
            {"message": "Session is invalid. Please reconnect."},
            room=subject_id,
        )
        return

    pressed_keys = data["pressed_keys"]

    # No keys pressed, don't execute other logic.
    if len(pressed_keys) == 0:
        return
    elif len(pressed_keys) > 1:
        if not CONFIG.game_has_composite_actions:
            pressed_keys = pressed_keys[:1]
        else:
            pressed_keys = generate_composite_action(pressed_keys)

    game = _get_existing_game(subject_id)

    if game is None:
        return

    if not any([k in CONFIG.action_mapping for k in pressed_keys]):
        return

    action = None
    for k in pressed_keys:
        if k in CONFIG.action_mapping:
            action = CONFIG.action_mapping[k]
            break

    assert action is not None

    game.enqueue_action(subject_id, action)


def generate_composite_action(pressed_keys) -> list[tuple[str]]:

    # TODO(chase): set this in the config so we don't recalculate every time
    max_composite_action_size = max(
        [len(k) for k in CONFIG.action_mapping.keys() if isinstance(k, tuple)] + [0]
    )

    if max_composite_action_size > 1:
        composite_actions = [
            action for action in CONFIG.action_mapping if isinstance(action, tuple)
        ]

        composites = [
            tuple(sorted(action_comp))
            for action_comp in itertools.combinations(
                pressed_keys, max_composite_action_size
            )
        ]
        for composite in composites:
            if composite in composite_actions:
                pressed_keys = [composite]
                break

    return pressed_keys


@socketio.on("reset_complete")
def handle_reset_complete(data):
    subject_id = flask.request.sid
    client_session_id = data.get("session_id")

    if not is_valid_session(client_session_id):
        flask_socketio.emit(
            "invalid_session",
            {"message": "Session is invalid. Please reconnect."},
            room=subject_id,
        )
        return

    game_id = data["room"]

    game = GAMES.get(game_id, None)

    if game is None:
        return

    # Set the event for the corresponding player
    try:
        RESET_EVENTS[game_id][subject_id].set()
    except:
        print("keyerror!!!", subject_id)
        print(RESET_EVENTS[game_id].keys())

    # Check if all players have completed their reset
    if all(event.is_set() for event in RESET_EVENTS[game_id].values()):
        game.reset_event.set()  # Signal to the game loop that reset is complete


@socketio.on("pong")
def on_pong(data):
    socketio.emit(
        "pong_response", {"timestamp": data.get("timestamp")}, room=flask.request.sid
    )


def run_game(game: remote_game.RemoteGame):
    end_status = [remote_game.GameStatus.Inactive, remote_game.GameStatus.Done]
    game.reset()
    render_game(game)
    if CONFIG.input_mode == configuration_constants.InputModes.PressedKeys:
        socketio.emit("request_pressed_keys", {})
    socketio.sleep(1 / game.config.fps)

    while game.status not in end_status:

        with game.lock:
            game.tick()

        render_game(game)
        if CONFIG.input_mode == configuration_constants.InputModes.PressedKeys:
            socketio.emit("request_pressed_keys", {})
        socketio.sleep(1 / game.config.fps)

        if game.status == remote_game.GameStatus.Reset:
            socketio.emit(
                "game_reset",
                {
                    "timeout": CONFIG.reset_timeout,
                    "config": CONFIG.to_dict(serializable=True),
                    "room": game.game_id,
                },
                room=game.game_id,
            )

            game.reset_event.wait()

            # Clear the events for each player
            for event in RESET_EVENTS[game.game_id].values():
                event.clear()

            # Clear the game reset event
            game.reset_event.clear()

            with game.lock:
                game.reset()

            render_game(game)

            socketio.sleep(1 / game.config.fps)

    with game.lock:
        if game.status != remote_game.GameStatus.Inactive:
            game.tear_down()

        socketio.emit(
            "end_game",
            {"redirect_url": CONFIG.redirect_url, "timeout": CONFIG.redirect_timeout},
            room=game.game_id,
        )

        _cleanup_game(game)


def render_game(game: remote_game.RemoteGame):
    state = None
    encoded_image = None
    if CONFIG.env_to_state_fn is not None:
        # generate a state object representation
        state = CONFIG.env_to_state_fn(game.env, CONFIG)
    else:
        # Generate a base64 image of the game and send it to display
        assert cv2 is not None, "Must install cv2 to use default image rendering!"
        assert (
            game.env.render_mode == "rgb_array"
        ), "Env must be using render more rgb_array!"
        game_image = game.env.render()
        _, encoded_image = cv2.imencode(".png", game_image)
        encoded_image = base64.b64encode(encoded_image).decode()

    hud_text = CONFIG.hud_text_fn(game) if CONFIG.hud_text_fn is not None else None

    # TODO(chase): this emits the same state to every player in a room, but we may want
    #   to have different observations for each player. Figure that out (maybe state is a dict
    #   with player_ids and their respective observations?).
    socketio.emit(
        "environment_state",
        {
            "state": state,
            "game_image_base64": encoded_image,
            "step": game.tick_num,
            "hud_text": hud_text,
        },
        room=game.game_id,
    )


def on_exit():
    # Force-terminate all games on server termination
    for game_id in GAMES:
        socketio.emit("end_game", {}, room=game_id)


def run(config):
    global app, CONFIG, FREE_IDS, MAX_CONCURRENT_GAMES, FREE_MAP
    CONFIG = config
    MAX_CONCURRENT_GAMES = CONFIG.max_concurrent_games

    # Global queue of available IDs. This is how we sync game creation and keep track of how many games are in memory
    FREE_IDS = queue.Queue(maxsize=CONFIG.max_concurrent_games)

    # Initialize our ID tracking data
    # TODO(chase): Starting at 1 fixed broadcasting to players on the instructions page. Is the default room 0?
    for i in range(1, CONFIG.max_concurrent_games + 1):
        FREE_IDS.put(i)
        FREE_MAP[i] = True
        RESET_EVENTS[i] = utils.ThreadSafeDict()

    atexit.register(on_exit)

    # app.wsgi_app = profiler.ProfilerMiddleware(app.wsgi_app)

    socketio.run(
        app,
        log_output=app.config["DEBUG"],
        port=CONFIG.port,
        host=CONFIG.host,
    )
