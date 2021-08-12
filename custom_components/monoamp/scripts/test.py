import websocket
import time

def on_message(ws, message):
    print(message)
    print("******")



url = "ws://192.168.2.128:4446/pianod/?protocol=json"

ws = websocket.WebSocket(url)

# time.sleep(2)

ws.send("ROOM LIST")

ws.run_forever()