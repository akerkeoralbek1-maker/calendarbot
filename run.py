import threading

from web_auth import app
from bot import main


def run_flask():
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    main()
