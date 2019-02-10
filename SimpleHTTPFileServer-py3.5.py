import asyncio
import pathlib
import time
import socket
import sys
import os
import shutil
import html
import platform
import re
from urllib import parse
from aiohttp import web

# Uncomment the following line if os.sendfile is buggy or doesn't work
# web.FileResponse._sendfile = web.FileResponse._sendfile_fallback

__version__ = '1.6.0'
__author__ = 'spcharc'

_change_log = '''Change Log:
v1.6 - Multiple bindings.
v1.5 - Copy / move files.
v1.4 - Rename items.
v1.3 - Read-only and hidden shares.
v1.2 - Multiple shared folders.
v1.1 - Upload multiple files.
v1.0 - Initial version.'''


class Server:
    '''
    Requirements:
        python >= 3.6
        aiohttp

    Usage (use Server.run blocking API):
            ./SimpleHTTPFileServer.py [DIR] [-p NUM] [-ro]
            :DIR:     folder to share
            :NUM:     port to use
            :ro flag: read-only mode
            # type ./SimpleHTTPFileServer.py -h for help
        - or -
            import SimpleHTTPFileServer as SVR
            server = SVR.Server( ... )
            server.add_share( ... )
            server.run()

        To stop the server: press Ctrl + C

    Usage (run it asynchronously)
            import SimpleHTTPFileServer as SVR
            server = SVR.Server( ... )
            async with server:
                do_something
    '''
    _html0 = ('<!DOCTYPE html>\n<html>\n<head>\n<title>Simple HTTP File Server'
              '</title>\n<meta name="author" content="{0}">\n<meta name="gener'
              'ator" content="{1}-Ver{2}">\n</head>').format(
                                            __author__,
                                            platform.python_implementation(),
                                            platform.python_version())
    _html1 = '<body>\n<h2>Index of {0}</h2>\n{1}<hr>\n<table>'
    _html2 = '<tr>\n<td width="80%">{0}</td>\n<td width="20%">{1}</td>\n</tr>'
    _html3 = '</table>\n<hr>'
    _html4 = ('<form enctype="multipart/form-data" method="post">Upload:\n<inp'
              'ut type="file" name="0" multiple="multiple" required="required"'
              '>\n<input type="submit" value="Upload file(s)">\n</form><br>\n<'
              'form enctype="multipart/form-data" method="post">New DIR:\n<inp'
              'ut type="text" name="1" required="required">\n<input type="subm'
              'it" value="Create DIR">\n</form><br>\n<form enctype="multipart/'
              'form-data" method="post">Delete:\n<input type="text" name="2" r'
              'equired="required">\n<input type="submit" value="Confirm Deleti'
              'on">\n</form><br>\n<form enctype="multipart/form-data" method="'
              'post">Rename:\n<input type="text" name="3" required="required">'
              '->\n<input type="text" name="4" required="required">\n<input ty'
              'pe="submit" value="Rename">\n</form><br>\n<form enctype="multip'
              'art/form-data" method="post">\n<input type="radio" name="5" val'
              'ue="cp" required="required">Copy\n<input type="radio" name="5" '
              'value="mv" required="required">Move\n<input type="text" name="6'
              '" required="required">to this folder\n<input type="submit" valu'
              'e="Paste">\n</form>\n<hr>')
    _html5 = ('<p title="{0}"><i><small>Simple HTTP File Server version {1}</s'
              'mall></i></p>\n</body>\n</html>').format(_change_log,
                                                        __version__)
    _html6 = (_html0 + '\n<body>\n<h2>Home Page</h2>\n<p>{0}</p>\n<hr>\n{1}\n<'
              'hr>' + _html5)
    _html7 = '<a href="{0}">{1}</a>'
    _html8 = '<p>{0}</p>\n'
    _re_pattern = re.compile('/{2,}')

    def __init__(self, *, listen=(('0.0.0.0', 8080),), loop=None,
                 logfile=Ellipsis, timef='%b/%d %H:%M:%S', wait=30):
        '''Args:

        :listen:  list or tuple. IP addresses and ports to listen on
        :loop:    None for the current loop asyncio.get_event_loop(), or an
                  asyncio.AbstractEventLoop object
        :logfile: None to disable logging. or a file-like object that supports
                  object.write(str). Please be aware that not all information
                  is written into logfile. Such as traceback of exceptions
                  produced by aiohttp module
        :timef:   str. Time format in log. Used in time.strftime()
        :wait:    int. Wait a maximum number of sec(s) for connections to close
                  when __aexit__ is awaited
        '''
        if loop is None:
            loop = asyncio.get_event_loop()
        if logfile is Ellipsis:
            logfile = sys.stdout
        try:
            assert isinstance(listen, (list, tuple))
            for _b, _p in listen:
                assert 0 < _p < 65536
            assert isinstance(loop, asyncio.AbstractEventLoop)
            assert (hasattr(logfile, 'write') or logfile is None)
            assert isinstance(timef, str)
            assert isinstance(wait, int) and wait >= 0
        except AssertionError as exc:
            raise ValueError('Arguments error. Please see docstring.') from exc

        self._fd = {}
        self._ro = set()
        self._hd = set()
        self._listen = tuple(listen)
        self._loop = loop
        self._logfile = logfile
        self._timef = timef
        self._wait = wait
        self._server = web.Server(self._request_handler, loop=self._loop)
        self._lpsvr = []  # Will be filled when starts listening

    def add_share(self, name, path, *, hidden=False, readonly=False):
        '''Args:

        :name:     str. name of share
        :path:     str or pathlib.Path object. Path of target folder (could
                   also be a file)
        :hidden:   bool. Hidden shares can only be accessed by typing the
                   correct path in browser address bar
        :readonly: bool. Cannot write to read-only shared folders (this option
                   has no effect on shared files)
        '''
        if isinstance(path, str):
            path = pathlib.Path(path)
        n = pathlib.Path(name)
        assert isinstance(name, str) and isinstance(path, pathlib.Path) and \
            isinstance(hidden, bool) and isinstance(readonly, bool) and \
            len(n.parts) == 1 and n.name != '..' and not n.anchor
        path = path.resolve()
        self._fd[name] = path
        if hidden:
            self._hd.add(name)
        else:
            self._hd.discard(name)
        if readonly:
            self._ro.add(name)
        else:
            self._ro.discard(name)

    def remove_share(self, name):
        if name in self._fd:
            del self._fd[name]
            self._hd.discard(name)
            self._ro.discard(name)
        else:
            raise ValueError('Share not found.')

    @staticmethod
    def _local_path_check(path, root, strict_flag):
        try:
            if strict_flag:
                res = path.resolve()
            else:
                l = []
                while not path.exists():
                    l.append(path.name)
                    path = path.parent
                res = path.resolve()
                for i in reversed(l):
                    res = res / i
            assert res.relative_to(root) is not None
        except FileNotFoundError:
            raise web.HTTPNotFound
        except Exception:
            raise web.HTTPForbidden
        return res

    def _web_path(self, pathstr, method=None):
        assert pathstr[0] == '/'
        pathstr = pathstr[1:]
        share_name, sep, rest = pathstr.partition('/')
        if len(share_name) == 0:
            assert len(sep) == 0 and len(rest) == 0
            root = None
        elif share_name in self._fd:
            root = self._fd[share_name]
        else:
            raise web.HTTPNotFound
        readonly = True if root is None else share_name in self._ro
        if method is not None:
            if readonly and method != 'GET':
                raise web.HTTPMethodNotAllowed(method, ['GET'])
            if method != 'GET' and method != 'POST':
                raise web.HTTPMethodNotAllowed(method, ['GET', 'POST'])
        rest = pathlib.Path(rest)
        if rest.anchor:
            raise web.HTTPForbidden
        return share_name, root, readonly, rest

    @staticmethod
    def _windows_check(pathstr):
        if platform.system() == 'Windows':
            if '\\' in pathstr:
                raise web.HTTPNotFound

    async def _post_upload(self, reader, field, path, root):
        r = ['Upload Result:']
        while field is not None and field.name == '0':
            filename = field.filename
            try:
                f = pathlib.Path(filename)
                if len(f.parts) != 1 or f.anchor:
                    return 'Illegal filename'
                newp = self._local_path_check(path / f, root, False)
                with newp.open('wb') as f:
                    while True:
                        chunk = await field.read_chunk()
                        if len(chunk) == 0:
                            break
                        f.write(chunk)
            except Exception as exc:
                self._log('Error: receive {0} failed {1}: {2}'
                                   .format(filename, type(exc).__name__), exc)
                r.append(html.escape('Failed: {0}'.format(filename)))
                try:
                    os.remove(newp)
                except Exception:
                    pass
                break
            else:
                r.append(html.escape('Successful: {0}'.format(filename)))
                field = await reader.next()
        await reader.release()
        return '<br>'.join(r)

    async def _post_mkdir(self, reader, field, path, root):
        folder_name = pathlib.Path((await field.read()).decode('utf-8'))
        try:
            if len(folder_name.parts) != 1 or folder_name.anchor:
                return 'Illegal input'
            newp = self._local_path_check(path / folder_name, root, False)
            newp.mkdir()
        except Exception as exc:
            self._log('Error: create dir {0} failed {1}: {2}'
                                .format(folder_name, type(exc).__name__, exc))
            return html.escape('Create DIR Failed: {0}'
                                            .format(folder_name.as_posix()))
        finally:
            await reader.release()
        return html.escape('DIR {0} Created.'.format(folder_name.as_posix()))

    async def _post_delete(self, reader, field, path, root):
        to_del = pathlib.Path((await field.read()).decode('utf-8'))
        try:
            if len(to_del.parts) != 1 or to_del.anchor:
                return 'Illegal input'
            newp = self._local_path_check(path / to_del, root, True)
            if newp.is_symlink() or newp.is_file():
                newp.unlink()
            elif newp.is_dir():
                newp.rmdir()
        except Exception as exc:
            self._log('Error: delete {0} failed {1}: {2}'
                                    .format(to_del), type(exc).__name__, exc)
            return html.escape('Deletion Failed: {0}'
                                                    .format(to_del.as_posix()))
        finally:
            await reader.release()
        return html.escape('Deleted: {0}'.format(to_del.as_posix()))

    async def _post_rename(self, reader, field, path, root):
        fr = pathlib.Path((await field.read()).decode('utf-8'))
        field = await reader.next()
        try:
            if field is None or field.name != '4':
                return 'POST data error.'
            to = pathlib.Path((await field.read()).decode('utf-8'))
            if len(fr.parts) != 1 or len(to.parts) != 1 or fr.anchor or \
                    to.anchor:
                return 'Illegal input'
            newfr = self._local_path_check(path / fr, root, True)
            newto = self._local_path_check(path / to, root, False)
            if newto.exists():
                return 'Target exists.'
            newfr.rename(newto)
        except Exception as exc:
            self._log('Error: rename {0} failed {1}: {2}'
                                        .format(fr, type(exc).__name__, exc))
            return html.escape('Rename Failed: {0}'.format(fr.as_posix()))
        finally:
            await reader.release()
        return html.escape('Renamed: {0}'.format(to.as_posix()))

    async def _post_copy_move(self, request, reader, field, path, root):
        method = (await field.read()).decode('utf-8')
        try:
            if method != 'cp' and method != 'mv':
                return 'POST data error.'
            field = await reader.next()
            if field.name != '6':
                return 'POST data error.'
            src = (await field.read()).decode('utf-8')
            self._windows_check(src)
            webpath = self._re_pattern.sub('/',
                                           parse.urljoin(request.path, src))
            rname, root2, ro, rest = self._web_path(webpath)
            if ro and method == 'mv':
                return 'Target read-only. Move not allowed.'
            if len(rest.parts) == 0:
                if root2.is_dir():
                    return 'Not Implemented.'
                elif root2.is_file():
                    if method == 'mv':
                        return 'Cannot move shared file.'
                    p = root2
                    name = rname
                else:
                    raise ValueError('Unknown type.')
            else:
                p = self._local_path_check(root2 / rest, root2, True)
                if p.is_dir():
                    return 'Not Implemented.'
                elif p.is_file():
                    name = p.name
                else:
                    raise ValueError('Unknown type.')
            t = self._local_path_check(path / name, root, False)
            if t.exists():
                return 'Target exists'
            if method == 'cp':
                shutil.copy(p, t, follow_symlinks=False)
            else:
                shutil.move(p, t, copy_function=shutil.copy)
        except Exception as exc:
            self._log('Error: cp/mv {0} failed {1}: {2}'
                                        .format(src, type(exc).__name__, exc))
            return html.escape('Paste failed: {0}'.format(src))
        finally:
            await reader.release()
        return html.escape('Pasted: {0}'.format(name))

    def _get_mainpage(self):
        resp = []
        for name, path in self._fd.items():
            if name in self._hd:
                continue
            if path.is_dir():
                suff = '/'
            elif path.is_file():
                suff = ''
            else:
                raise web.HTTPInternalServerError
            resp.append(self._html7.format(parse.quote(name + suff),
                                           html.escape(name + suff)))
        return web.Response(text=self._html6.format('List of Shared Folders',
                                                    '<br>\n'.join(resp)),
                            content_type='text/html')

    def _get_dir(self, request, rname, path, ro, root, post_result):
        if not request.path.endswith('/'):
            raise web.HTTPMovedPermanently(request.path + '/')
        if post_result:
            post_result = self._html8.format(post_result)
        resp = [self._html0,
                self._html1.format(html.escape(
                    pathlib.Path(
                        rname,
                        path.relative_to(root)
                    ).as_posix()),
                    post_result),
                self._html2.format('<b>Name</b>', '<b>Size</b>')]
        body = [[], [], {}]
        # python 3.6 dict: keys are kept in insertion order
        try:
            resp.append(self._html2.format(self._html7.format(
                '../', '../'), 'DIR'))
            for item in path.iterdir():
                if item.is_symlink():
                    body[0].append(item.name)
                elif item.is_dir():
                    body[1].append(item.name)
                elif item.is_file():
                    body[2][item.name] = item.stat().st_size
                else:
                    raise web.HTTPInternalServerError
        except PermissionError:
            raise web.HTTPForbidden
        resp.extend(self._html2.format(
            self._html7.format(parse.quote(item_name),
                               html.escape(item_name + '@')),
            'LNK')
            for item_name in sorted(body[0]))
        resp.extend(self._html2.format(
            self._html7.format(parse.quote(item_name + '/'),
                               html.escape(item_name + '/')),
            'DIR')
            for item_name in sorted(body[1]))
        resp.extend(self._html2.format(
            self._html7.format(parse.quote(item_name),
                               html.escape(item_name)),
            size)
            for item_name, size in sorted(body[2].items()))
        resp.append(self._html3)
        if not ro:
            resp.append(self._html4)
        # resp.append(self._html7.format('/', 'Home Page'))
        resp.append(self._html5)
        return web.Response(text='\n'.join(resp), content_type='text/html')

    def _get_file(self, request, path):
        if request.path.endswith('/'):
            raise web.HTTPMovedPermanently(request.path[:-1])
        return web.FileResponse(path)

    async def _post_handler(self, request, path, root):
        if request.content_type != 'multipart/form-data' or not path.is_dir():
            raise web.HTTPBadRequest
        reader = await request.multipart()
        field = await reader.next()
        if field is None:
            raise web.HTTPBadRequest
        if field.name == '0':
            return await self._post_upload(reader, field, path, root)
        elif field.name == '1':
            return await self._post_mkdir(reader, field, path, root)
        elif field.name == '2':
            return await self._post_delete(reader, field, path, root)
        elif field.name == '3':
            return await self._post_rename(reader, field, path, root)
        elif field.name == '5':
            return await self._post_copy_move(request,
                                              reader, field, path, root)
        elif field.name == '6':
            return 'Select: Copy or Move.'
        else:
            raise web.HTTPBadRequest

    async def _request_handler(self, request):
        if request.query_string:
            raise web.HTTPBadRequest
        self._windows_check(request.path)
        path = self._re_pattern.sub('/', request.path)
        if path != request.path:
            raise web.HTTPMovedPermanently(path)
        self._log(request.remote, '->', request.host, request.method,
                  request.path, request.headers.get('Range', ''))
        rname, root, ro, to_handle = self._web_path(path, request.method)
        if root is None:
            return self._get_mainpage()
        path = self._local_path_check(root / to_handle, root, True)
        post_result = ''
        if request.method == 'POST':
            try:
                post_result = await self._post_handler(request, path, root)
            except web.HTTPException:  # web.HTTPError would also work
                raise
            except Exception:
                raise web.HTTPBadRequest
        if path.is_dir():
            return self._get_dir(request, rname, path, ro, root, post_result)
        elif path.is_file():
            return self._get_file(request, path)
        else:
            raise web.HTTPInternalServerError

    def _log(self, *content):
        if self._logfile is not None:
            self._logfile.write('{0} - {1}\n'.format(
                time.strftime(self._timef), " ".join(map(str, content))))

    def run(self):
        self._loop.run_until_complete(self.__aenter__())
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            print()
        finally:
            self._loop.run_until_complete(self.__aexit__())

    async def __aenter__(self):
        if len(self._lpsvr) == 0: # if it is already running, skip
            try:
                for i, j in (self._listen):
                    self._lpsvr.append(await self._loop.create_server(
                                                           self._server, i, j))
                    self._log('Serving on {0}:{1}'.format(i, j))
            except Exception:
                raise ValueError('Port {0} already in use.'.format(j)) from \
                                                                           None
            self._log('Shared Folder(s):')
            for name, path in self._fd.items():
                self._log('{0}: {1}'.format(name, path) +
                          ('[hidden]' if name in self._hd else '') +
                          ('[readonly]' if name in self._ro else ''))
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 53))
                ip = s.getsockname()[0]
                self._log('Host IPv4:', ip)
            except Exception:
                pass
            finally:
                if s is not None:
                    s.close()
                    s = None
            try:
                s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                s.connect(('2001:4860:4860::8888', 53))
                ip = s.getsockname()[0]
                self._log('Host IPv6:', ip)
            except Exception:
                pass
            finally:
                if s is not None:
                    s.close()
                    s = None

    async def __aexit__(self, exc_type=None, exc_val=None, exc_traceback=None):
        if len(self._lpsvr) > 0: # if no port / no addr to listen on, skip
            self._log('Exit in {0} sec(s).'.format(self._wait))
            await self._server.shutdown(self._wait)
            while self._lpsvr:
                i = self._lpsvr.pop()
                i.close()
            self._log('Exiting.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='A simple HTTP file server. '
        'Designed mainly for file sharing via Wi-Fi.',
        epilog='Security not guaranteed. Use it with caution.')
    parser.add_argument(
        'rootdir', nargs='?', help='Root dir of your server. But it could also'
        ' be a file. Default: {0}'.format(pathlib.Path.cwd()),
        type=pathlib.Path, default='.')
    parser.add_argument(
        '-p', '--port', nargs='?', help='Port to listen on. Default: 8080',
        type=int, default=8080)
    parser.add_argument(
        '-ro', '--readonly', action='store_true', help='Start server under rea'
        'd-only mode. If a file is being shared, this option does nothing.')
    args = parser.parse_args()
    server = Server(listen=(('0.0.0.0', args.port), ))
    server.add_share('Shared_Folder', args.rootdir, readonly=args.readonly)
    server.run()
