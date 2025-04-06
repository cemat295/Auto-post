from flask import Flask, render_template_string, request, redirect
import json, time, threading, os, requests

app = Flask(__name__)
CONFIG_PATH = "config.json"
posting_active = False
config = {
    "token": "",
    "use_webhook": False,
    "webhook_url": "",
    "channels": []
}

def load_config():
    global config
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print("[ERROR] config.json is broken. Using default config.")
    else:
        save_config()

def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

@app.route("/", methods=["GET"])
def index():
    return render_template_string(html_template, config_json=json.dumps(config, indent=4), config=config)

@app.route("/save-config", methods=["POST"])
def save():
    token = request.form.get("token")
    webhook_url = request.form.get("webhook_url")
    use_webhook = True if request.form.get("use_webhook") else False

    channel_id = request.form.get("channel_id")
    message = request.form.get("message")
    try:
        hours = int(request.form.get("hours") or 0)
        minutes = int(request.form.get("minutes") or 0)
        seconds = int(request.form.get("seconds") or 0)
    except:
        hours = minutes = seconds = 0

    interval = hours * 3600 + minutes * 60 + seconds
    action = request.form.get("action")

    if token:
        config["token"] = token
    config["webhook_url"] = webhook_url
    config["use_webhook"] = use_webhook

    if action == "add" and channel_id and message:
        config["channels"].append({"id": channel_id, "message": message, "interval": interval})
    elif action == "edit":
        for ch in config["channels"]:
            if ch["id"] == channel_id:
                ch["message"] = message
                ch["interval"] = interval
    elif action == "remove":
        config["channels"] = [ch for ch in config["channels"] if ch["id"] != channel_id]

    save_config()
    return redirect("/")

@app.route("/load-config", methods=["POST"])
def load():
    load_config()
    return redirect("/")

@app.route("/start", methods=["POST"])
def start():
    global posting_active
    if not posting_active:
        posting_active = True
        threading.Thread(target=auto_post, daemon=True).start()
    return redirect("/")

@app.route("/stop", methods=["POST"])
def stop():
    global posting_active
    posting_active = False
    return redirect("/")

@app.route("/test-webhook", methods=["POST"])
def test_webhook():
    if config["webhook_url"]:
        requests.post(config["webhook_url"], json={"content": "Test Webhook from Controller"})
    return redirect("/")

def auto_post():
    while posting_active:
        for ch in config["channels"]:
            if not posting_active:
                break
            try:
                if config["use_webhook"] and config["webhook_url"]:
                    requests.post(config["webhook_url"], json={"content": ch["message"]})
                else:
                    url = f"https://discord.com/api/v9/channels/{ch['id']}/messages"
                    headers = {
                        "Authorization": config["token"],
                        "Content-Type": "application/json"
                    }
                    data = {
                        "content": ch["message"]
                    }
                    res = requests.post(url, headers=headers, json=data)
                    print(f"[{res.status_code}] Posted to {ch['id']}: {ch['message']}")
            except Exception as e:
                print(f"Error posting to {ch['id']}: {e}")
            time.sleep(ch["interval"])
        time.sleep(1)

html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Auto Poster Controller</title>
    <style>
        body { font-family: Arial; padding: 20px; text-align: center; }
        .section { border: 1px solid #ccc; padding: 15px; margin: 15px auto; width: 90%; max-width: 500px; text-align: left; }
        .section-title { font-weight: bold; margin-bottom: 10px; }
        input[type="text"], input[type="number"], textarea { width: 100%; padding: 5px; margin-top: 5px; }
        button { padding: 10px 20px; margin: 5px; }
        pre { background-color: #f4f4f4; padding: 10px; overflow: auto; }
    </style>
</head>
<body>
    <h1>Auto Poster</h1>
    <form method="POST" action="/save-config">
        <div class="section">
            <div class="section-title">Discord Token Settings</div>
            <input type="password" name="token" placeholder="Discord Token" id="tokenInput" value="{{ config.get('token', '') }}">
            <br><input type="checkbox" onclick="toggleToken()"> Show Token
        </div>

        <div class="section">
            <div class="section-title">Post Settings</div>
            <input type="text" name="channel_id" placeholder="Channel ID">
            <textarea name="message" placeholder="Message..."></textarea>
            Interval:<br>
            <input type="number" name="hours" placeholder="Hours" min="0">
            <input type="number" name="minutes" placeholder="Minutes" min="0">
            <input type="number" name="seconds" placeholder="Seconds" min="0"><br><br>
            <button name="action" value="add">Add Channel</button>
            <button name="action" value="edit">Edit Channel</button>
            <button name="action" value="remove">Remove Channel</button>
        </div>

        <div class="section">
            <div class="section-title">Webhook Settings</div>
            <input type="checkbox" name="use_webhook" {% if config.get('use_webhook') %}checked{% endif %}> Use Webhook<br>
            <input type="text" name="webhook_url" placeholder="Webhook URL" value="{{ config.get('webhook_url', '') }}">
            <br><br><button formaction="/test-webhook" formmethod="post">Test Webhook</button>
        </div>

        <div class="section">
            <div class="section-title">Current Config</div>
            <pre>{{ config_json }}</pre>
            <button formaction="/load-config" formmethod="post">Load Config</button>
            <button type="submit">Save Config</button>
        </div>
    </form>

    <form method="POST" action="/start">
        <button style="background-color: lightgreen;">Start</button>
    </form>

    <form method="POST" action="/stop">
        <button style="background-color: salmon;">Stop</button>
    </form>

    <script>
        function toggleToken() {
            var x = document.getElementById("tokenInput");
            x.type = x.type === "password" ? "text" : "password";
        }
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    load_config()
    app.run(debug=True, host="0.0.0.0", port=5000)
