# SPDX-License-Identifier: MIT
# Copyright (C) 2020 Athena Martin.

"""
Server module; handles the client's commands.

NOT THREAD-SAFE. Use asyncio instead.
"""

import json
import asyncio
from typing import List, Mapping
from . import common

class _ServerObjectMembership:
    server: object = None # Actually a Server.
    object_val: object = None # Actually an Object.
    object_id: int = None
    subscriptions: List[str] = None
    
    def __init__(self, server, object_val, object_id):
        self.server = server
        self.object_val = object_val
        self.object_id = object_id
        self.subscriptions = []
        
class NotAllowed(Exception):
    pass
        
class Object:
    """
    A server-side object.

    Can be indexed to access the properties. Can be a member of multiple servers. Automatically (and asynchronously) informs all containing servers when a property is set.
    """
    properties: Mapping[str, object] = None
    servers: List[_ServerObjectMembership] = None

    async def update_servers(self, property, value):
        """
        Inform all containing servers that a property has been updated.
        """
        for membership in self.servers:
            asyncio.create_task(membership.server.update(membership.object_id, property, value)) # Do these concurrently. We don't care about the results.

    def add_server(self, server, object_id):
        """
        Add a server to the object's list of containing servers. You should probably call the server's add_object() instead.
        """
        membership = _ServerObjectMembership(server, self, object_id)
        self.servers.append(membership)
        return membership

    def remove_server(server):
        """
        Remove a server from the object's list of containing servers. You should probably call the server's remove_object() instead.
        """
        for membership in servers:
            if membership.server is server:
                servers.remove(membership)
    
    def __getitem__(self, key):
        return self.properties[key]

    def __setitem__(self, key, value):
        self.properties[key] = value # TODO: Read-only properties.
        asyncio.create_task(self.update_servers(key, value)) # Is it okay to never await a task? Probably.

    def __init__(self):
        self.properties = {}
        self.servers = []
        
class Server(common.ApplicationLayer):
    """
    The server-side application-layer code. Invoked by the SessionLayer when messages are received, and invokes it in return to send them back.
    
    Your server should subclass this to implement additional messages (async def mtype_<mtype value>(**kwargs)) and probably to register itself somewhere. You can send an update with the update() method (or by setting a value on an object in this server) and a reply with the reply() method.
    """
    objects: Mapping[int, _ServerObjectMembership] = None
    server_name: str = None
    specialization_name: str = None
    
    def add_object(self, id: int, object: Object):
        """
        Add an object to this server.
        """
        membership = object.add_server(self, id)
        self.objects[id] = membership # FIXME: This should be an _ServerObjectMembership
        self.objects[0].object_val["objects"].append(id)
        asyncio.create_task(self.objects[0].object_val.update_servers("objects", self.objects[0].object_val["objects"]))
    
    async def receive(self, datagram: str):
        message: dict = json.loads(datagram)
        func_name = "mtype_" + message["mtype"]
        
        try:
            func = getattr(self, func_name)
        except AttributeError:
            await self.unknown_mtype(**message)
            return
        
        await func(**message)

    async def update(self, object_id: int, property: str, value):
        """
        Send an update message. You probably just want to set the property on the object and let its __setitem__() call this for you.
        """
        if property in self.objects[object_id].subscriptions:
            await self.session.send(json.dumps({
                "mtype": "update",
                "object": object_id,
                "property": property,
                "value": value
            }))

    async def reply(self, token: int, status: str, **kwargs: dict):
        """
        Send a reply. Keyword arguments are included in the message.
        """
        if token is None:
            return
        
        message = {
            "mtype": "reply",
            "token": token,
            "status": status
        }
        
        for k, v in kwargs.items():
            message[k] = v
        
        await self.session.send(json.dumps(message))

    async def mtype_set(self, token: int, object: int, property: str, value, **kwargs):
        if not object in self.objects:
            await self.reply(token, "no such object")
            return

        try:
            self.objects[object].object_val[property] = value
            await self.reply(token, "success")
        except NotAllowed:
            await self.reply(token, "not allowed")
        except IndexError:
            await self.reply(token, "no such property")

    async def mtype_get(self, token: int, object: int, property: str, **kwargs):
        if not object in self.objects:
            await self.reply(token, "no such object")
            return

        try:
            await self.reply(token, "success", value=self.objects[object].object_val[property])
        except IndexError:
            await self.reply(token, "no such property")

    async def mtype_subscribe(self, token: int, object: int, properties: List[str], **kwargs):
        if not object in self.objects:
            await self.reply(token, "no such object")
            return

        for property in properties: # TODO: Non-subscribable properties.
            if not property in self.objects[object].subscriptions:
                self.objects[object].subscriptions.append(property)
        # TODO: Handle non-existant subscribe properties?
        
        await self.reply(token, "success")

    async def mtype_unsubscribe(self, token: int, object: int, properties: List[str], **kwargs):
        if not object in self.objects:
            await self.reply(token, "no such object")
            return

        for property in properties:
            if not property in self.objects[object].subscriptions:
                try:
                    self.objects[object].subscriptions.remove(property)
                except ValueError: None

        await self.reply(token, "success")
        
    # TODO: remove_object()

    def __init__(self, session: common.SessionLayer, server_name: str, specialization_name: str):
        super().__init__(session)
        self.server_name = server_name
        self.specialization_name = specialization_name
        self.objects = {}

        universe = Object()
        universe["type"] = "universe"
        universe["version"] = 1
        universe["objects"] = []
        universe["time"] = 0
        self.add_object(0, universe)

        asyncio.create_task(self.session.send(json.dumps({
            "mtype": "identify",
            "specialization": self.specialization_name,
            "server": self.server_name
        })))
