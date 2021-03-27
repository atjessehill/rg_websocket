from rgws.interface import WebsocketClient
import json, logging, asyncio


class SimpleClientInterface(WebsocketClient):
    def __init__(self, **kwargs):
        super(SimpleClientInterface, self).__init__(**kwargs)

    """
    This is business logic for client, basically in this example
    we just connects to server and trying to call `example_func` once
    then exits.
    """

    async def _producer(self, websocket):
        logging.debug(await self.example_func("blo"))
        # if you want to pass function with arguments, you can use functools.partial(func, args)
        logging.debug(await self.read_data_stream(websocket, self.stream_func))


if __name__ == "__main__":
    c = SimpleClientInterface(host="localhost", port=8080)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.run())
    loop.run_forever()
