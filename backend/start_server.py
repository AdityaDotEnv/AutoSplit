import sys

sys.path.insert(0, ".")
from app import app, socketio

if __name__ == "__main__":
    print("Starting server on http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)
