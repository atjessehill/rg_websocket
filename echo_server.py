from rgws.interface import WebsocketServer
import json, asyncio


class SimpleServerInterface(WebsocketServer):
    def __init__(self, **kwargs):
        super(SimpleServerInterface, self).__init__(**kwargs)
        self.secret_value = "MY_SUPER_SECRET_KEY"
        self._register(self.get_super_secret)
        self._register(self.start_record)
        self._register(self.stop_record)

    async def _consumer(self, websocket, message):
        await websocket.send(await self.dispatch(message))

    async def get_super_secret(self):
        return json.dumps({"resp": self.secret_value})

    async def start_record(self):
        return json.dumps({"resp": "started"})

    async def stop_record(self):
        return json.dumps({"resp": "stopped"})


if __name__ == "__main__":
    s = SimpleServerInterface(host="localhost", port=8080)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(s.run(compression=None))
    loop.run_forever()
