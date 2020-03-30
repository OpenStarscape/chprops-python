# SPDX-License-Identifier
# Copyright 2020 Athena Martin

"""
Client module; allows the client to manipulate objects more easily.

NOT THREAD-SAFE. Use asyncio instead.
"""

import json
import asyncio
from typing import List, Mapping, Any, Callable
from . import common

class Object:
    """
    A client-side object.

    Can be indexed to access the properties, but this happens asynchronously; you must await the result of obj["property"] to actually get the property value.
    """
    client = None
    object_id: int = 0
    subscriptions: Mapping[str, Callable[[int, str, Any], Any]] = None

    async def get(self, property: str) -> Any:
        """
        Get the value of one of the object's properties.
        """
        return await self.client.get(self.object_id, property)

    async def set(self, property: str, value: Any):
        """
        Set the value of one of the object's properties.
        """
        return await self.client.set(self.object_id, property, value)

    async def subscribe(self, callbacks: Mapping[str, Callable[[int, str, Any], Any]]):
        """
        Register each callback provided as the handler for a subscription to the property whose name is its key and inform the server.
        """
        properties = []
        for property, callback in callbacks.items():
            self.subscriptions[property] = callback
        await self.client.subscribe(self.object_id, properties)

    async def unsubscribe(self, properties: List[str]):
        """
        Remove subscriptions for the specified properties.
        """
        await self.client.unsubscribe(self.object_id, properties)
        for property in properties:
            del self.subscriptions[property]

    async def update(self, property, value):
        """
        Handle an update of a property.
        """
        await self.subscriptions[property](self.object_id, property, value)
    
    def __getitem__(self, key):
        return asyncio.create_task(self.get(key))

    def __setitem__(self, key, value):
        asyncio.create_task(self.set(key, value))

    def __init__(self, client, object_id):
        self.client = client
        self.object_id = object_id
        self.subscriptions = {}

class PendingRequest():
    event: asyncio.Event = None
    message: Mapping[str, Any] = None

    def __init__(self):
        self.event = asyncio.Event()

class Client(common.ApplicationLayer):
    objects: Mapping[int, Object] = None
    outstanding_replies: Mapping[int, asyncio.Event] = None
    next_token = 1

    def generate_token(self) -> int:
        token = self.next_token
        self.next_token = token + 1
        return token
    
    async def receive(self, datagram: str):
        message: dict = json.loads(datagram)
        func_name = "mtype_" + message["mtype"]

        try:
            func = getattr(self, func_name)
        except AttributeError:
            await self.unknown_mtype(**message)

        await func(**message)

    async def request(self, **kwargs: dict) -> dict:
        """
        Request something from the server and await to return the reply. All keyword arguments are passed as fields of the message, but a token is generated automatically.
        """
        token = self.generate_token()
        kwargs["token"] = token
        
        req = PendingRequest()
        self.outstanding_replies[token] = req

        await self.session.send(json.dumps(kwargs))
        await req.event.wait()

        del self.outstanding_replies[token]
        return req.message

    async def set(self, object_id: int, property: str, value: Any):
        await self.request(mtype="set", object=object_id, property=property, value=value)
        # TODO: Handle errors.

    async def get(self, object_id: int, property: str):
        return (await self.request(mtype="get", object=object_id, property=property))["value"]
        # TODO: Handle errors.

    async def subscribe(self, object_id: int, properties: List[str]):
        await self.session.send(json.dumps({
            "mtype": "subscribe",
            "token": None,
            "object": object_id,
            "properties": properties
        }))
    
    async def mtype_update(self, object: int, property: str, value):
        await self.objects[object].update(property, value)    

    async def mtype_reply(self, **kwargs: dict):
        token = kwargs["token"]
        self.outstanding_replies[token].message = kwargs
        self.outstanding_replies[token].event.set()

    def __getitem__(self, key: int):
        if not key in self.objects:
            self.objects[key] = Object(self, key)
        return self.objects[key]
    
    def __init__(self, session):
        super().__init__(session)
        self.objects = {}
        self.outstanding_replies = {}
