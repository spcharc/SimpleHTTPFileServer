# SimpleHTTPFileServer
A simple http file sharing server written in python (3.6+ required) with aiohttp

Description
=
A simple server for file uploading and downloading. Renaming, copying and moving are also supported

Usage
=
Just download SimpleHTTPFileServer.py and use it.

Requires python version >= 3.6, and aiohttp library (`pip install aiohttp`)

#### Command line: (share a single folder quickly and easily)
```
python SimpleHTTPFileServer.py [somePath/toShare/]
```
The path defaults to the current working dir. It could be set to a file
`-p [PORT]` option could be used to specify a port (default 8080).
`-ro` option enables read-only mode.
The server will be created on `0.0.0.0:[PORT]`

#### Python: (create a customized server)
```
import SimpleHTTPFileServer as sfs
import asyncio

eventloop = asyncio.get_event_loop()
bind = ('::1', 7000), ('127.0.0.1', 8000), ('192.168.1.2', 9000)

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
##### `__init__` method: constructor
* `loop` allows third party event loops (default `asyncio.get_event_loop()`)

* `listen` takes a list or tuple of some address-port pairs, and will try to listen on all of them (default: `('0.0.0.0',8080),`)

* `wait` specifies how many seconds the server waits when terminating, before a forced shutdown (default: 30)

* `logfile` can be specified to None, and no log will be written (default: writes to stdout)

##### `add_share` method adds an shared folder (could also be a file)
It needs a name (displayed in the web page, and used in web path) and a file-system path for this entry(string or pathlib.Path object)

* `hidden` flag: it won't be displayed in the web page if set to `True`

* `readonly` flag: uploading / renaming / copying / moving is disabled if set to `True`

##### `remove_share` method could be used to remove an existing shared folder. It takes only the name as argument.

##### Finally, `run` method starts the handling work
It could be terminated by `Ctrl + C`, but it will wait for existing connections to finish before exiting. The maximum time could be set when creating the `Server` instance

About security
=
No https support. So the connections are not secured.

It is designed to disallow viewing / modifying folder outside of shared ones. Don't rely on this.

Read-only shares could not be changed. Don't rely on this.

Any contribution is welcomed.
