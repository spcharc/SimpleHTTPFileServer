# SimpleHTTPFileServer
A simple http file sharing server written in python (3.6+ required) with aiohttp

Description
=
A simple server for file uploading and downloading. Renaming, copying and moving are also supported

Usage
=
Just download SimpleHTTPFileServer.py and use it.

### Requirements

Requires python version >= 3.6, and aiohttp library (`pip install aiohttp`)

It works with pure python environment, tested to work in [Pythonista](https://itunes.apple.com/us/app/pythonista-3/id1085978097) (an iOS App)

### Command line: (share a single folder quickly and easily)
```
python SimpleHTTPFileServer.py [somePath/toShare/]
```
The path defaults to the current working dir. It could be set to a file

`-p [PORT]` option could be used to specify a port (default 8080).

`-ro` option enables read-only mode.

The server will be created on `0.0.0.0:[PORT]`

### Python: (create a customized server)
```
import SimpleHTTPFileServer as sfs
import asyncio

eventloop = asyncio.get_event_loop()
bind = ('::1', 7000, None), ('127.0.0.1', 8000, None), ('192.168.1.2', 9000, None)

server = sfs.Server(loop=eventloop,
                    listen=bind,
                    wait=10,
                    logfile=None)

import pathlib
to_share = pathlib.Path('some/path/')

server.add_share('favicon.ico', 'WebRoot/index.ico', hidden=True)
server.add_share('shared', to_share, readonly=True)

server.run()
```
Everything is in the `Server` class:
##### `Server.__init__` method: constructor
* `loop` allows third party event loops (default `asyncio.get_event_loop()`)

* `listen` takes a list (or tuple) of list (or tuple), inner list should have a length of 3. Its format is address, port and ssl context. It will listen on all of them (default: `('0.0.0.0',8080, None),`) ssl context could be created as:
```
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('chain.pem', 'privkey.pem')
```

* `wait` specifies how many seconds the server waits when terminating, before a forced shutdown (default: 30)

* `logfile` can be specified to None, and no log will be written (default: writes to stdout)

##### `Server.add_share` method adds an shared folder (could also be a file)
It needs a name (displayed in the web page, and used in web path) and a file-system path for this entry(string or pathlib.Path object)

* `hidden` flag: it won't be displayed in the web page if set to `True`

* `readonly` flag: uploading / renaming / copying / moving is disabled if set to `True`

##### `Server.remove_share` method could be used to remove an existing shared folder. It takes only the name as argument.

##### Finally, `Server.run` method starts the handling work
It could be terminated by `Ctrl + C`, but it will wait for existing connections to finish before exiting. The maximum time could be set when creating the `Server` instance

##### You may also use `async with Server([...])` to run it asynchronously

About security
=
No https support. So the connections are not secured.

It is designed to disallow viewing / modifying folder outside of shared ones. Don't rely on this.

Read-only shares could not be changed. Don't rely on this.

Any contribution is welcomed.
