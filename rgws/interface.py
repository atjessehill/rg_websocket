import asyncio
import websockets
from abc import ABC, abstractmethod
from typing import Callable, Union
from types import FunctionType
import logging
import json
from enum import Enum
import inspect
import itertools

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.INFO)


async def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class ErrorCode(Enum):
    UNKNOWN = 0
    METHOD_NOT_FOUND = 1
    BAD_ARGS = 2
    NOT_A_DATA_STREAM = 3


class Error(object):
    async def __new__(self, *args, **kwargs):
        error_code = kwargs.get("code", ErrorCode.UNKNOWN)
        yield json.dumps({"error": error_code.value})


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

    async def get_methods(self):
        fs = []
        for name, f in self.methods.items():
            args = list(filter(lambda x: x != "self", inspect.signature(f).parameters))
            fs.append({"cmd": name, "args": args})
        return json.dumps(fs)

    async def dispatch(self, msg, **kwargs):
        cmd = msg.get("cmd", None)
        if not cmd:
            return Error(ErrorCode.UNKNOWN)
        args = msg.get("args", {})
        func = self.methods.get(cmd, None)
        if not func:
            logging.debug(f"{func} {cmd}")
            return Error(ErrorCode.METHOD_NOT_FOUND)
        try:
            ret = func(*args)
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
        self.ws = None

    # Call function at remote server by name
    def __getattr__(self, name):
        async def wrapper(*args):
            logging.debug(f"{args}")
            await self.ws.send(json.dumps({"cmd": name, "args": args}))
            return json.loads(await self.ws.recv())

        return wrapper

    @abstractmethod
    async def _producer(self, websocket):
        raise NotImplementedError("Implement producer at your own class")

    # Read websocket if you except to receive a data stream
    async def read_data_stream(self, websocket, func):
        await func()
        chunks_united = []
        while True:
            data = json.loads(await websocket.recv())
            chunk = data.get("chunk", None)
            if not chunk:
                break
            chunks_united.append(chunk)
        return list(itertools.chain(*chunks_united))

    async def run(self):
        self.ws = await websockets.connect(self.uri)
        return await self._producer(self.ws)


class WebsocketServer(JSONRPC):
    """
    Generic Websocket Server for any RG module
    """

    def __init__(self, host: str = None, port: int = None, **kwargs):
        super(WebsocketServer, self).__init__(**kwargs)
        self._register(self.get_methods)
        self.host = host
        self.port = port

    @abstractmethod
    async def _consumer(
        self, websocket: websockets.WebSocketCommonProtocol, message: dict
    ):
        raise NotImplementedError("Implement consumer at your own class")

    async def handler(self, websocket: websockets.WebSocketCommonProtocol, path: str):
        async for message in websocket:
            try:
                msg = json.loads(message)
            except json.decoder.JSONDecodeError:
                continue
            await self._consumer(websocket, msg)

    # Make data stream and give the async generator to user.
    # Use return for data_stream instead of yield
    async def make_data_stream(self, data):
        yield json.dumps({"chunk": None})
        async for chunk in chunks(data, 100):
            yield json.dumps({"chunk": chunk})
        yield json.dumps({"chunk": None})

    def run(self, **kwargs):
        return websockets.serve(
            self.handler,
            self.host,
            self.port,
            max_size=None,
            **kwargs,
        )
