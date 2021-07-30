import asyncio
from aiohttp import web, WSMsgType, WSMessage, ClientSession
from abc import ABC, abstractmethod
from typing import Callable, Union
from types import FunctionType
import logging
import json
from enum import Enum
import inspect
import itertools


class ErrorCode(Enum):
    UNKNOWN = 0
    NO_METHOD_SPECIFIED = 1
    METHOD_NOT_FOUND = 2
    BAD_ARGS = 3
    NOT_A_DATA_STREAM = 4


class Error(object):
    async def __new__(self, *args, **kwargs):
        error_code = kwargs.get("code", ErrorCode.UNKNOWN)
        yield {"error": error_code.value}


class JSONRPC(ABC):
    """
    Tiny JSON-RPC implementation
    """

    def __init__(self, **kwargs):
        super(JSONRPC, self).__init__(**kwargs)
        self.methods = {}

    # function should be a generator!
    def _register(self, func: Callable) -> bool:
        if not callable(func):
            return False
        logging.debug(f"{func.__name__} registered!")
        self.methods.update({func.__name__: func})
        return True

    def _unregister(self, func: Union[str, Callable]) -> bool:
        if callable(func) and self.methods.get(func.__name__, None):
            self.methods.pop(func.__name__, None)
            return True
        elif self.methods.get(func, None):
            self.methods.pop(func)
            return True
        return False

    async def dispatch(self, msg):
        cmd = msg.get("cmd", None)
        if not cmd:
            return Error(ErrorCode.NO_METHOD_SPECIFIED)
        args = msg.get("args", {})
        func = self.methods.get(cmd, None)
        if not func:
            return Error(ErrorCode.METHOD_NOT_FOUND)
        try:
            ret = func(*args.get("pos", []), **args.get("kw", {}))
            if asyncio.iscoroutinefunction(func):
                ret = await ret
        except TypeError:
            logging.error(
                f"User passed wrong arguments to {cmd}: {args}", exc_info=True
            )
            return Error(ErrorCode.BAD_ARGS)
        return ret


class WebsocketClient(JSONRPC):
    def __init__(self, host: str = None, port: int = None, **kwargs):
        super(WebsocketClient, self).__init__(**kwargs)
        self.host = host
        self.port = port
        self.uri = f"ws://{self.host}:{self.port}"

    # Call function at remote server by name
    def __getattr__(self, name):
        async def wrapper(*args, **kwargs):
            await self.ws.send_json({"cmd": name, "args": {"pos": args, "kw": kwargs}})
            return (await self.ws.receive()).json()

        return wrapper

    @abstractmethod
    async def _producer(self, ws):
        raise NotImplementedError("Implement producer at your own class")

    async def run(self, **kwargs):
        session = ClientSession()

        retry = 5
        while True:

            try:
                async with session.ws_connect(self.uri, max_msg_size=10 ** 100) as ws:
                    self.ws = ws
                    await self._producer(ws)
                    await session.close()
                    break
            except Exception as e:
                print(f"Server is not running yet retrying in {retry} seconds...")

            await asyncio.sleep(retry)

        logging.debug("connection closed")


class WebsocketServer(JSONRPC):
    """
    Generic Websocket Server for any RG module
    """

    def __init__(self, host: str = None, port: int = None, **kwargs):
        super(WebsocketServer, self).__init__(**kwargs)
        self._register(self.get_methods)
        self.host = host
        self.port = port

    # Function to list registered method
    async def get_methods(self):
        fs = []
        for name, f in self.methods.items():
            args = list(filter(lambda x: x != "self", inspect.signature(f).parameters))
            fs.append({"cmd": name, "args": args})
        yield fs

    @abstractmethod
    async def _consumer(self, websocket: web.WebSocketResponse, message: WSMessage):
        raise NotImplementedError("Implement consumer at your own class")

    async def handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            logging.debug(msg.data)
            if msg.type == WSMsgType.TEXT:
                await self._consumer(ws, msg.json())
            elif msg.type == WSMsgType.ERROR:
                logging.error(f"ws connection closed with exception {ws.exception()}")
        logging.debug("websocket connection closed")

        return ws

    def run(self, **kwargs):
        app = web.Application()
        app.add_routes([web.get("/", self.handler)])
        web.run_app(app, host=self.host, port=self.port, **kwargs)
