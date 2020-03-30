# SPDX-License-Identifier: MIT
# Copyright (C) 2020 Athena Martin

"""
Stream session layer; implements the session layer for stream transport clients and servers.

NOT THREAD-SAFE. Use asyncio instead.
"""

import asyncio
from . import common

class StreamSession(common.SessionLayer):
    """
    Stream session layer. Uses asyncio's asynchronous networking.
    """
    reader: asyncio.StreamReader = None
    writer: asyncio.StreamWriter = None

    async def send(self, datagram: str):
        await self.writer.drain()
        self.writer.write(bytes(datagram + "\n", "utf-8"))

    async def run(self):
        datagram = b""
        while True:
            try:
                datagram = datagram + await self.reader.readuntil()
                asyncio.create_task(self.application.receive(datagram))
                datagram = b""
            except asyncio.IncompleteReadError as e:
                datagram = datagram + e.partial
        # TODO: Don't leak self (and spin CPU?) when the connection dies.
                
    def __init__(self, reader, writer, *args, **kwargs):
        self.reader = reader
        self.writer = writer
        super().__init__(*args, **kwargs)

async def connect_inet(host, port, *args, tls=False, tls_host=None, **kwargs):
    """
    Connects as a client to the specified Internet server using TCP and (if tls set to True) TLS. If specified, tls_server_name is used for server name checks. All other arguments are passed through to the session and application layers.
    """
    (reader, writer) = await asyncio.open_connection(host, port, ssl=tls, server_hostname=tls_host)
    session = StreamSession(reader, writer, *args, **kwargs)
    asyncio.create_task(session.run())
    return session

async def server_inet(port, *args, **kwargs):
    """
    Runs an Internet server using TCP. A separate session and application layer are created for each client. All arguments are passed through to the session and application layers each time they are created.
    """
    async def launch(reader, writer):
        await StreamSession(reader, writer, *args, **kwargs).run()
    asyncio.create_task(asyncio.start_server(launch, port=port)) # TODO: Support TLS.

async def connect_unix(path, *args, **kwargs):
    """
    Connects as a client to the specified Unix-domain sockets path. All other arguments are passed through to the session and application layers.
    """
    (reader, writer) = await asyncio.open_unix_connection(path)
    session = StreamSession(reader, writer, *args, **kwargs)
    asyncio.create_task(session.run())
    return session

async def server_unix(path, *args, **kwargs):
    """
    Runs a Unix-domain sockets server on the specified path. A separate session and application layer are created for each client. All arguments are passed through to the session and application layers each time they are created.
    """
    async def launch(reader, writer):
        await StreamSession(reader, writer, *args, **kwargs).run()
    asyncio.start_server(launch, path)
    
