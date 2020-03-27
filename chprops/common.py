# SPDX-License-Identifier: MIT
# Copyright (C) 2020 Athena Martin

"""
Common module; interface code used by both the client and the server.

NOT THREAD-SAFE. Use asyncio instead.
"""

class ApplicationLayer:
    session: object = None # Actually a SessionLayer.

    async def receive(self, datagram: str):
        """
        Handles a message received at the session layer.

        Concrete subclasses of ApplicationLayer must implement this.
        """
        raise NotImplementedError("Must implement receive() in subclass of ApplicationLayer.")
    
    def __init__(self, session):
        self.session = session

class SessionLayer:
    """
    A session layer.

    Your session layer should subclass this and invoke the application layer when messages are recieved.
    """
    application: ApplicationLayer

    async def send(self, datagram: str):
        """
        Send the datagram to the other end.

        Concrete subclasses of SessionLayer must implement this.
        """
        raise NotImplementedError("Must implement send() in subclass of SessionLayer.")

    async def run(self):
        """
        Drive the session layer until the connection is closed, receiving messages and handing them to the application layer.

        Concrete subclasses of SessionLayer must implement this.
        """
        raise NotImplementedError("Must implement run() in subclass of SessionLayer.")
    
    def __init__(self, Application, *args, **kwargs):
        """
        Initialize self and create an Application using self with arguments args and kwargs.
        """
        self.application = Application(self, *args, **kwargs)
