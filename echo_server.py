from rgws.interface import WebsocketServer
import json, asyncio


class SimpleServerInterface(WebsocketServer):
    def __init__(self, **kwargs):
        super(SimpleServerInterface, self).__init__(**kwargs)
        self._register(self.example_func)
        self._register(self.stream_func)

    """
    This overrides _consumer method in WebsocketServer, there should
    business logic be placed if any. At this point we are just 
    dispatching function from message and sending result back.
    """

    async def _consumer(self, websocket, message):
        ret = await self.dispatch(message)
        async for gen in ret:
            await websocket.send(gen)

    async def example_func(self, bla):
        yield json.dumps({"resp": bla})

    async def stream_func(self):
        data = [0.0] * 2 ** 20
        return self.make_data_stream(data)


if __name__ == "__main__":
    s = SimpleServerInterface(host="localhost", port=8080)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(s.run(compression=None))
    loop.run_forever()
