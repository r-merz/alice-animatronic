from flask import Flask, request, jsonify

import alice

app = Flask(__name__)


# Initialize Alice's persistent conversation/state once
alice.alice_lore = alice.load_alice_lore()
alice.load_memory()
alice_state = alice.load_alice_state()
spotify_controller = alice.AliceSpotify()


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    if not message:
        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    print("iPhone:", message)

    try:
        result = alice.process_alice_message(
            message,
            alice_state=alice_state,
            spotify_controller=spotify_controller,
            response_language="english",
        )

        print(
            "Alice router result:",
            result,
        )

        return jsonify(
            result
        )

    except Exception as error:
        print(
            "Alice API error:",
            type(error).__name__,
            error,
        )

        return jsonify({
            "type": "error",
            "response": (
                "Alice encountered an error."
            ),
            "error": str(error),
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )