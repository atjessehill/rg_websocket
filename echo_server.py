from rgws.interface_aiohttp import WebsocketServer
import json, asyncio


class SimpleServerInterface(WebsocketServer):
    def __init__(self, **kwargs):
        super(SimpleServerInterface, self).__init__(**kwargs)
        self._register(self.example_func)
        self._register(self.big_data_func)

    """
    This overrides _consumer method in WebsocketServer, there should
    business logic be placed if any. At this point we are just 
    dispatching function from message and sending result back.
    """

    async def _consumer(self, ws, message):
        ret = await self.dispatch(message)
        async for msg in ret:
            await ws.send_json(msg)

    async def example_func(self, bla):
        yield {"resp": bla}

    async def stream_fubig_data_funcnc(self):
        data = [0.0] * 2 ** 20
        yield {"resp": data}


if __name__ == "__main__":
    s = SimpleServerInterface(host="localhost", port=8080)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(s.run(compression=None))
    loop.run_forever()
