var socket = io();


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


$(() => {
    $('#startButton').click( () => {
        $("#startButton").hide();
        $("#startButton").attr("disabled", true);
        socket.emit("join", {});

    })
})


socket.on("start_game", function(data) {
    $("#welcomeHeader").hide();
    $("#welcomeText").hide();
    $("#instructions").hide();
    $("#waitroomText").hide();
    $("#gameHeaderText").show();
    $("#gamePageText").show();
    $("#gameContainer").show();


    let config = data.config;

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

    enable_key_listener()
    graphics_start(graphics_config);
})

socket.on("waiting_room", function(data) {
    $("#waitroomText").show();
    $("#waitroomText").append(`<h4>There are ${data.cur_num_players} in the lobby, waiting for ${data.players_needed} more.</h4>`);
})

socket.on("game_reset", function(data) {
    graphics_end()


    // Initialize game
    let config = data.config;
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


    startResetCountdown(data.timeout, function() {
        // This function will be called after the countdown
        enable_key_listener();
        graphics_start(graphics_config);
    });


})


function startResetCountdown(timeout, callback) {
    var timer = Math.floor(timeout / 1000); // Convert milliseconds to seconds
    var interval = setInterval(function () {
        if (timer <= 0) {
            clearInterval(interval);
            $("#reset-game").hide();
            $("#reset-game").text("")
            if (callback) callback(); // Call the callback function
        } else {
            var minutes = parseInt(timer / 60, 10);
            var seconds = parseInt(timer % 60, 10);

            minutes = minutes < 10 ? "0" + minutes : minutes;
            seconds = seconds < 10 ? "0" + seconds : seconds;
            $("#reset-game").text("Waiting for the next round to start in " + minutes + ":" + seconds);
            $("#reset-game").show();
        }
        timer--;
    }, 1000);
}

socket.on("create_game_failed", function(data) {
    $("#welcomeHeader").show();
    $("#welcomeText").show();
    $("#instructions").show();
    $("#waitroomText").hide();

     $("#startButton").show();
     $("#startButton").attr("disabled", false);


    let err = data['error']
    $('#errorText').append(`<h4>Sorry, game creation code failed with error: ${JSON.stringify(err)}</>`);
})


socket.on('environment_state', function(data) {
    // Draw state update
    updateState(data);
});

socket.on('end_game', function(data) {
    // Hide game data and display game-over html
    graphics_end();
    disable_key_listener()

    $('#finalPageHeaderText').show()
    $('#finalPageText').show()
    $("#gameHeaderText").hide();
    $("#gamePageText").hide();
    $("#gameContainer").hide();


    // Set a timeout for redirection
    setTimeout(function() {
        // Redirect to the specified URL after the timeout
        window.location.href = data.redirect_url;
    }, data.redirect_timeout); // 5000 milliseconds = 5 seconds
});





var pressedKeys = {};

socket.on('request_pressed_keys', function(data) {
    socket.emit('send_pressed_keys', {'pressed_keys': Object.keys(pressedKeys)});
});

function enable_key_listener() {
    $(document).on('keydown', function(event) {
        if (pressedKeys[event.key]) {
            return; // Key is already pressed, so exit the function
        }

        pressedKeys[event.key] = true; // Add key to pressedKeys when it is pressed
        // shouldSendPressedKeys = true;
    });

    $(document).on('keyup', function(event) {
        delete pressedKeys[event.key]; // Remove key from pressedKeys when it is released
    });
}


function disable_key_listener() {
        $(document).off('keydown');
        $(document).off('keyup');
}