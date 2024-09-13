import * as ui_utils from './ui_utils.js';



export class RemoteGame {
    constructor(config) {
        this.config = config;
        this.micropip = null;
        this.pyodideReady = false;
        this.initialize(); 
        this.objects_to_render = [];
        this.observations = [];
        this.render_state = null;
        this.num_episodes = 0;
        this.max_episodes = config.num_episodes;
        this.step_num = 0;
        this.max_steps = 1000; // TODO(chase): get from config/env
        this.cumulative_rewards = {};
        this.shouldReset = true;
        this.state = null;
    }

    isDone(){
        return this.state === "done";
    }

    async initialize() {
        this.pyodide = await loadPyodide();

        await this.pyodide.loadPackage("micropip");
        this.micropip = this.pyodide.pyimport("micropip");

        if (this.config.packages_to_install !== undefined) {
            console.log("Installing packages via micropip: ", this.config.packages_to_install);
            await this.micropip.install(this.config.packages_to_install);
        }

        // The code executed here must instantiate an environment `env`
        const env = await this.pyodide.runPythonAsync(`
${this.config.environment_initialization_code}
env
        `);

        if (env == undefined) {
            throw new Error("The environment was not initialized correctly. Ensure the the environment_initialization_code correctly creates an `env` object.");
        }

        this.state = "ready";
        this.pyodideReady = true;
    }

    async reset() {
        this.shouldReset = false;
        const result = await this.pyodide.runPythonAsync(`
obs, infos = env.reset()
render_state = env.render()
obs, infos, render_state
        `);
        let [obs, infos, render_state] = await this.pyodide.toPy(result).toJs();
        render_state = {
            "game_state_objects": render_state.map(item => convertUndefinedToNull(item))
        };
        this.step_num = 0;
        this.shouldReset = false;

        // Iterate over the keys of obs and set cumulative rewards to be 0 for each ID
        for (let key of obs.keys()) {
            this.cumulative_rewards[key] = 0;
        }

        ui_utils.showHUD();
        ui_utils.updateHUDText(this.getHUDText());


        return [obs, infos, render_state]
    }


    async step(actions) {
        const pyActions = this.pyodide.toPy(actions);
        const result = await this.pyodide.runPythonAsync(`
agent_actions = {int(k): v for k, v in ${pyActions}.items()}
obs, rewards, terminateds, truncateds, infos = env.step(agent_actions)
render_state = env.render()
obs, rewards, terminateds, truncateds, infos, render_state
        `);

        // Convert everything from python objects to JS objects
        let [obs, rewards, terminateds, truncateds, infos, render_state] = await this.pyodide.toPy(result).toJs();
        
        for (let [key, value] of rewards.entries()) {
            this.cumulative_rewards[key] += value;
        }

        this.step_num = this.step_num + 1;

        render_state = {
            "game_state_objects": render_state.map(item => convertUndefinedToNull(item))
        };

        ui_utils.updateHUDText(this.getHUDText());

        // Check if the episode is complete
        const all_terminated = Array.from(terminateds.values()).every(value => value === true);
        const all_truncated = Array.from(truncateds.values()).every(value => value === true);

        if (all_terminated || all_truncated) {
            this.num_episodes += 1;

            if (this.num_episodes >= this.max_episodes) {
                this.state = "done";
            } else {
                this.shouldReset = true;
            }
            
        }

        return [obs, rewards, terminateds, truncateds, infos, render_state]
    };

    getHUDText() {
        let score = Object.values(this.cumulative_rewards)[0];
        let time_left = (this.max_steps - this.step_num) / this.config.fps;

        let formatted_score = score.toString().padStart(2, '0');
        let formatted_time_left = time_left.toFixed(1).toString().padStart(5, '0');

        let hud_text = `Score: ${formatted_score} | Time left: ${formatted_time_left}s`;

        return hud_text
    };
};



// Helper function to convert Proxy(Map) to a plain object
function convertProxyToObject(obj) {
    if (obj instanceof Map) {
        return Array.from(obj).reduce((acc, [key, value]) => {
            acc[key] = value instanceof Object ? this.convertProxyToObject(value) : value;
            return acc;
        }, {});
    } else if (obj instanceof Object) {
        return Object.keys(obj).reduce((acc, key) => {
            acc[key] = obj[key] instanceof Object ? this.convertProxyToObject(obj[key]) : obj[key];
            return acc;
        }, {});
    }
    return obj; // Return value directly if it's neither Map nor Object
}


// Helper function to convert all `undefined` values in an object to `null`
function convertUndefinedToNull(obj) {
    if (typeof obj !== 'object' || obj === null) {
        // Return the value as is if it's not an object or is already null
        return obj;
    }

    for (let key in obj) {
        if (obj[key] === undefined) {
            obj[key] = null; // Convert undefined to null
        } else if (typeof obj[key] === 'object') {
            // Recursively apply the conversion to nested objects
            obj[key] = convertUndefinedToNull(obj[key]);
        }
    }

    return obj;
}