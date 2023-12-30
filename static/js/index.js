var socket = io();


function startGame() {
    // Hide the start button
    document.getElementById('startButton').style.display = 'none';

    // Show the game container
    document.getElementById('gameContainer').style.display = 'block';

    // Hide the start texts
    document.getElementById('startHeaderText').style.display = 'none';
    document.getElementById('startPageText').style.display = 'none';

    // Hide between episode texts
    document.getElementById('betweenEpisodeHeaderText').style.display = 'none';
    document.getElementById('betweenEpisodePageText').style.display = 'none';

    // Show the game texts
    document.getElementById('gameHeaderText').style.display = 'block';
    document.getElementById('gamePageText').style.display = 'block';

    socket.emit('request_config')
}


// TODO(chase): Rather than destroy the canvas at episode end, we can simply hide and show
//  it which whill prevent us from having to reload all of the assets at each episode. We'll
//  also need to reset object_map and clean up lingering objects from one episode to another.
function hideGameCanvas() {
    var canvas = document.getElementById('phaser-canvas');
    if (canvas) {
        canvas.style.display = 'none'; // Hide the canvas
    }
}

function showGameCanvas() {
    var canvas = document.getElementById('phaser-canvas');
    if (canvas) {
        canvas.style.display = 'block'; // Show the canvas
    }
}


socket.on('episode_complete', function(data) {
    // Destroy the game canvas
    graphics_end() // TODO: change to pause and only destroy if necessary

    // Remove game texts
    document.getElementById('gameHeaderText').style.display = 'none';
    document.getElementById('gamePageText').style.display = 'none';

    // Add between episode texts
    document.getElementById('betweenEpisodeHeaderText').style.display = 'block';
    document.getElementById('betweenEpisodePageText').style.display = 'block';

    // Show start button again
    document.getElementById('startButton').style.display = 'block';
})

socket.on('send_config', function(data) {
    let config = JSON.parse(data.config);

    // Initialize game
    let graphics_config = {
        'parent': 'gameContainer',
        'fps': {
            'target': config.fps,
            'forceSetTimeOut': true
        },
        'height': config.game_height,
        'width': config.game_width,
        'background': config.background,
        'state_init': config.state_init,
        'assets_dir': config.assets_dir,
        'assets_to_preload': config.assets_to_preload,
        'animation_configs': config.animation_configs,
    };

    graphics_start(graphics_config);
    socket.emit("play_single_episode", {})
})

// Add event listener to the start button
document.getElementById('startButton').addEventListener('click', startGame);

socket.on('environment_state', function(data) {
    // Draw state update
    updateState(data);
});

socket.on('end_game', function(data) {
    // Hide game data and display game-over html
    graphics_end();
});


var pressedKeys = {};
var shouldSendPressedKeys = false;

socket.on('request_pressed_keys', function(data) {
    socket.emit('send_pressed_keys', {'pressed_keys': Object.keys(pressedKeys)});

    // if (shouldSendPressedKeys) {
    //     console.log("sending pressed keys", Object.keys(pressedKeys))
    //     shouldSendPressedKeys = false;
    // }
});

$(document).on('keydown', function(event) {
    if (pressedKeys[event.key]) {
        return; // Key is already pressed, so exit the function
    }

    pressedKeys[event.key] = true; // Add key to pressedKeys when it is pressed
    // shouldSendPressedKeys = true;
});

$(document).on('keyup', function(event) {
    delete pressedKeys[event.key]; // Remove key from pressedKeys when it is released
    // shouldSendPressedKeys = true;
});


