import asyncio
import os
from typing import Any
from chprops import *

running_servers = []

class TestServer(server.Server):
    async def unknown_mtype(self, **kwargs):
        print("Unknown message (server):", kwargs)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        test_object = server.Object()
        test_object["type"] = "test"
        test_object["version"] = 1
        test_object["value"] = 6
        self.add_object(1, test_object)
        running_servers.append(self)

async def val_changed(object_id: int, property: str, value: Any):
    print("1.value changed: " + value)

class TestClient(client.Client):
    async def unknown_mtype(self, **kwargs):
        print("Unknown message (client):", kwargs)
    
    async def mtype_identify(self, server: str = None, specialization: str = None, **kwargs):
        print(f"Server identified as {server}, specialization {specialization}.")
        print("0.objects:", await self[0]["objects"])
        print("1.value:", await self[1]["value"])
        await self[1].subscribe(val_changed)

async def run_server_test():
    await stream.server_inet(9573, TestServer, "chprops test script", "none")

    await asyncio.sleep(5)
    running_servers[0].objects[0].object_val["value"] = 7
    await asyncio.sleep(5)
    running_servers[0].objects[0].object_val["value"] = 8

async def run_client_test():
    await stream.connect_inet("localhost", 9573, TestClient)

    await asyncio.sleep(15)

if os.fork() > 0:
    asyncio.run(run_server_test())
else:
    asyncio.run(run_client_test())
