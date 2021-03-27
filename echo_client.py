from rgws.interface import WebsocketClient
import json, logging, asyncio


class SimpleClientInterface(WebsocketClient):
    def __init__(self, **kwargs):
        super(SimpleClientInterface, self).__init__(**kwargs)

    async def _producer(self, websocket):
        while True:
            logging.debug(await self.get_super_secret())
            await asyncio.sleep(1)


if __name__ == "__main__":
    c = SimpleClientInterface(host="localhost", port=8080)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.run())
    loop.run_forever()
