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
import functools
from urllib import parse
from aiohttp import web

# Uncomment the following line if os.sendfile is buggy or doesn't work
# web.FileResponse._sendfile = web.FileResponse._sendfile_fallback

__version__ = '1.10.1'
__author__ = 'spcharc'

_change_log = '''Change Log:
v1.10 - Non-listing dir.
v1.9 - Sub-app.
v1.8 - Prefix.
v1.7 - HTTPS support.
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
    _html0 = ('<!DOCTYPE html>\n<html>\n<head>\n<title>{0}</title>\n<meta name'
              f'="author" content="{__author__}">\n<meta name="generator" cont'
              f'ent="{platform.python_implementation()}-Ver'
              f'{platform.python_version()}">\n<meta charset="UTF-8">\n<meta '
              'name="viewport" content="width=device-width, initial-scale=1.0"'
              '>\n<style>\na{text-decoration:none;}\nhr{width:500px;margin-lef'
              't:0px;}\ntable{border:1px solid silver;border-collapse:collapse'
              ';}\ntd,th{border:1px solid silver;}\n</style>\n</head>')
    _html1 = '<body>\n<h2>Index of {0}</h2>\n{1}<hr>\n<table>'
    _html2 = '<tr>\n<{0}>{1}</{0}>\n<{0}>{2}</{0}>\n</tr>'
    _html3 = '</table>\n<hr>'
    _html4 = ('<form enctype="multipart/form-data" method="post" accept-charse'
              't="UTF-8">Upload:\n<input type="file" name="0" multiple="multip'
              'le" required="required">\n<input type="submit" value="Upload fi'
              'le(s)">\n</form><br>\n<form enctype="multipart/form-data" metho'
              'd="post" accept-charset="UTF-8">New DIR:\n<input type="text" na'
              'me="1" required="required">\n<input type="submit" value="Create'
              ' DIR">\n</form><br>\n<form enctype="multipart/form-data" method'
              '="post" accept-charset="UTF-8">Delete:\n<input type="text" name'
              '="2" required="required">\n<input type="submit" value="Confirm '
              'Deletion">\n</form><br>\n<form enctype="multipart/form-data" me'
              'thod="post" accept-charset="UTF-8">Rename:\n<input type="text" '
              'name="3" required="required">->\n<input type="text" name="4" re'
              'quired="required">\n<input type="submit" value="Rename">\n</for'
              'm><br>\n<form enctype="multipart/form-data" method="post" accep'
              't-charset="UTF-8">\n<input type="radio" name="5" value="cp" req'
              'uired="required">Copy\n<input type="radio" name="5" value="mv" '
              'required="required">Move\n<input type="text" name="6" required='
              '"required">to this folder\n<input type="submit" value="Paste">'
              '\n</form>\n<hr>')
    _html5 = (f'<p title="{_change_log}"><i><small>Simple HTTP File Server ver'
              f'sion {__version__}</small></i></p>\n</body>\n</html>')
    _html6 = '\n<body>\n<h2>Home Page</h2>\n<p>{0}</p>\n<hr>\n{1}\n<hr>'
    _html7 = '<a href="{0}">{1}</a>'
    _html8 = '<p>{0}</p>\n'

    page_title = 'Simple HTTP File Server'
    home_page_headline = 'List of entries'

    _re_pattern = re.compile('/{2,}')

    _func_cpt = functools.partial(shutil.copytree, symlinks=True)
    _func_cp2 = functools.partial(shutil.copy2, follow_symlinks=False)
    # run in executor, pass named arguments in this way

    _size_units = (("B", "KB", "MB", "GB", "TB"),
                   ("B", "KiB", "MiB", "GiB", "TiB"))

    def __init__(self, *, listen=(('0.0.0.0', 8080, None),), loop=None,
                 logfile=Ellipsis, timef='%b/%d %H:%M:%S', wait=30,
                 prefix='/', https_redir=()):
        '''Args:

        :listen:      list or tuple. [IP address, port to listen on, ssl
                      context] (ssl context could be None to use plain http)
        :loop:        None for the current loop asyncio.get_event_loop(), or an
                      asyncio.AbstractEventLoop object
        :logfile:     None to disable logging. or a file-like object that
                      supports object.write(str). Please be aware that not all
                      information is written into logfile. Such as traceback of
                      exceptions produced by aiohttp module
        :timef:       str. Time format in log. Used in time.strftime()
        :wait:        int. Wait a maximum number of sec(s) for connections to
                      close when __aexit__ is awaited
        :prefix:      str. The main page could be deployed under a directory
        :https_redir: (str, int) list or tuple. Must have length 0 or 2. 1st
                      one is domain name, 2nd one is port number. If the user
                      doesn't use https, then return 301 Moved Permanently to
                      specified domian name and port. If it's empty, then
                      do not redirect user
        '''
        if loop is None:
            loop = asyncio.get_event_loop()
        if logfile is Ellipsis:
            logfile = sys.stdout
        try:
            assert isinstance(listen, (list, tuple))
            for _b, _p, _s in listen:
                assert 0 < _p < 65536, 'Port out of range'
            assert isinstance(loop, asyncio.AbstractEventLoop)
            assert (hasattr(logfile, 'write') or logfile is None)
            assert isinstance(timef, str)
            assert isinstance(wait, int) and wait >= 0
            assert isinstance(prefix, str) and prefix[0] == prefix[-1] == '/'
            assert isinstance(https_redir, (list, tuple))
            assert len(https_redir) == 0 or len(https_redir) == 2
        except AssertionError as exc:
            raise ValueError('Arguments error. Please see docstring.') from exc

        self._fd = {}
        self._ro = set()
        self._hd = set()
        self._ld = set()
        self._listen = tuple(listen)
        self._loop = loop
        self._logfile = logfile
        self._timef = timef
        self._wait = wait
        self._prefix = prefix
        self._https = tuple(https_redir)
        self._lpsvr = []  # Will be filled when starts listening

    def add_share(self, name, path, *, hidden=False, readonly=False,
                                       listdir=True):
        '''Args:

        :name:     str. name of share
        :path:     str or pathlib.Path object. Path of target folder (could
                   also be a file)
        :hidden:   bool. Hidden shares can only be accessed by typing the
                   correct path in browser address bar
        :readonly: bool. Cannot write to read-only shared folders (this option
                   has no effect on shared files)
        :listdir:  bool. Show content of dirs or not.
        '''
        if isinstance(path, str):
            path = pathlib.Path(path)
        n = pathlib.Path(name)
        assert isinstance(name, str) and isinstance(path, pathlib.Path) and \
            isinstance(hidden, bool) and isinstance(readonly, bool) and \
            len(n.parts) == 1 and n.name != '..' and not n.anchor
        path = path.resolve(strict=True)
        self._fd[name] = path
        if hidden:
            self._hd.add(name)
        else:
            self._hd.discard(name)
        if readonly:
            self._ro.add(name)
        else:
            self._ro.discard(name)
        if listdir:
            self._ld.add(name)
        else:
            self._ld.discard(name)

    def add_subapp(self, name, func, *, hidden=False):
        '''Args:

        :name:   str. name of app
        :func:   an async handler function called with func(request)
        :hidden: bool. Hidden apps can only be accessed by typing the correct
                 path in browser address bar'''
        assert callable(func)
        self._fd[name] = func
        if hidden:
            self._hd.add(name)
        else:
            self._hd.discard(name)

    def remove(self, name):
        'Remove an entry by its name'
        if name in self._fd:
            del self._fd[name]
            self._hd.discard(name)
            self._ro.discard(name)
        else:
            raise ValueError('Share not found.')

    @staticmethod
    def _local_path_check(path, root, strict_flag):
        try:
            res = path.resolve(strict=strict_flag)
            assert res.relative_to(root) is not None
        except FileNotFoundError:
            raise web.HTTPNotFound
        except Exception:
            raise web.HTTPForbidden
        return res

    def _web_path(self, pathstr, method=None):
        if not pathstr.startswith(self._prefix):
            raise web.HTTPMovedPermanently(self._prefix)
        pathstr = pathstr[len(self._prefix):]
        share_name, sep, rest = pathstr.partition('/')
        if len(share_name) == 0:
            assert len(sep) == 0 and len(rest) == 0
            root = None
        elif share_name in self._fd:
            root = self._fd[share_name]
        else:
            raise web.HTTPNotFound
        if callable(root):
            # in case it is a sub_app handler
            return root
        readonly = root is None or share_name in self._ro
        if method is not None:
            if (root is None or readonly) and method != 'GET':
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
                self._log(f'Error: receive {filename} failed '
                          f'{type(exc).__name__}: {exc}')
                r.append(html.escape(f'Failed: {filename}'))
                try:
                    newp.unlink()  # python 3.8: unlink(missing_ok=True)
                except Exception:
                    pass
                break
            else:
                r.append(html.escape(f'Successful: {filename}'))
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
            self._log(f'Error: create dir {folder_name} failed '
                      f'{type(exc).__name__}: {exc}')
            return html.escape(f'Create DIR Failed: {folder_name.as_posix()}')
        finally:
            await reader.release()
        return html.escape(f'DIR {folder_name.as_posix()} Created.')

    async def _post_delete(self, reader, field, path, root):
        to_del = pathlib.Path((await field.read()).decode('utf-8'))
        try:
            if len(to_del.parts) != 1 or to_del.anchor:
                return 'Illegal input.'
            newp = self._local_path_check(path / to_del, root, True)
            if newp.is_symlink() or newp.is_file():
                newp.unlink()
            elif newp.is_dir():
                await self._loop.run_in_executor(None, shutil.rmtree, newp)
        except Exception as exc:
            self._log(f'Error: delete {to_del} failed '
                      f'{type(exc).__name__}: {exc}')
            return html.escape(f'Deletion Failed: {to_del.as_posix()}')
        finally:
            await reader.release()
        return html.escape(f'Deleted: {to_del.as_posix()}')

    async def _post_rename(self, reader, field, path, root):
        fr = pathlib.Path((await field.read()).decode('utf-8'))
        field = await reader.next()
        try:
            if field is None or field.name != '4':
                return 'POST data error.'
            to = pathlib.Path((await field.read()).decode('utf-8'))
            if len(fr.parts) != 1 or len(to.parts) != 1 or fr.anchor or \
                    to.anchor:
                return 'Illegal input.'
            newfr = self._local_path_check(path / fr, root, True)
            newto = self._local_path_check(path / to, root, False)
            if newto.exists():
                return 'Target exists.'
            newfr.rename(newto)
        except Exception as exc:
            self._log(f'Error: rename {fr} failed '
                      f'{type(exc).__name__}: {exc}')
            return html.escape(f'Rename Failed: {fr.as_posix()}')
        finally:
            await reader.release()
        return html.escape(f'Renamed: {to.as_posix()}')

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
            wpres = self._web_path(webpath)
            if callable(wpres):        # if it's an handler
                return 'Invalid source'
            rname, root2, ro, rest = wpres
            if ro and method == 'mv':
                return 'Target read-only. Move not allowed.'
            if len(rest.parts) == 0:
                if root2.is_dir() or root2.is_file():
                    if method == 'mv':
                        return 'Cannot move shared entry.'
                    p = root2
                    name = rname
                else:
                    raise ValueError('Can only operate on a file or dir.')
            else:
                p = self._local_path_check(root2 / rest, root2, True)
                if p.is_dir() or p.is_file():
                    name = p.name
                else:
                    raise ValueError('Can only operate on a file or dir.')
            t = self._local_path_check(path / name, root, False)
            if t.exists():
                return 'Target exists'
            if p.is_dir():
                if method == 'cp':
                    await self._loop.run_in_executor(None, self._func_cpt, p, t)
                else:
                    await self._loop.run_in_executor(None, shutil.move, p, t)
            else:
                if method == 'cp':
                    await self._loop.run_in_executor(None, self._func_cp2, p, t)
                else:
                    await self._loop.run_in_executor(None, shutil.move, p, t)
        except Exception as exc:
            self._log(f'Error: cp/mv {src} failed '
                      f'{type(exc).__name__}: {exc}')
            return html.escape(f'Paste failed: {src}')
        finally:
            await reader.release()
        return html.escape(f'Pasted: {name}')

    def _get_mainpage(self):
        resp = []
        for name, path in self._fd.items():
            if name in self._hd:
                continue
            if callable(path):
                suff = ''
            elif path.is_dir():
                suff = '/'
            elif path.is_file():
                suff = ''
            else:
                pass # ignore ... (raise web.HTTPInternalServerError ?)
            resp.append(self._html7.format(parse.quote(name + suff),
                                           html.escape(name + suff)))
        return web.Response(text=''.join([self._html0.format(
                                              self.page_title),
                                          self._html6.format(
                                              self.home_page_headline,
                                              '<br>\n'.join(resp)),
                                          self._html5]),
                            content_type='text/html')

    def _size_for_human(size, binary, precision=2):
        base = 1024.0 if binary else 1000.0
        result = float(size)
        unit = 0
        while base < result and unit < 4:
            result /= base
        suffix = self._size_units[binary][unit]
        return f"{.{precision}f} {suffix}"

    def _get_dir(self, request, rname, path, ro, root, post_result):
        if not request.path.endswith('/'):
            raise web.HTTPMovedPermanently(request.path + '/')
        if post_result:
            post_result = self._html8.format(post_result)
        resp = [self._html0.format(self.page_title),
                self._html1.format(html.escape(
                    pathlib.Path(
                        rname,
                        path.relative_to(root)
                    ).as_posix()),
                    post_result),
                self._html2.format('th', 'Name', 'Size')]
        body = [[], [], {}]
        # python 3.6 dict: keys are kept in insertion order
        try:
            resp.append(self._html2.format('td',
                                           self._html7.format('../', '../'),
                                           'DIR'))
            if rname in self._ld:     # list content or not
                for item in path.iterdir():
                    if item.is_symlink():
                        body[0].append(item.name)
                    elif item.is_dir():
                        body[1].append(item.name)
                    elif item.is_file():
                        body[2][item.name] = item.stat().st_size
                    else:
                        pass  # just ignore ?raise web.HTTPInternalServerError?
        except PermissionError:
            raise web.HTTPForbidden
        resp.extend(self._html2.format(
            'td',
            self._html7.format(parse.quote(item_name),
                               html.escape(item_name + '@')),
            'LNK')
            for item_name in sorted(body[0]))
        resp.extend(self._html2.format(
            'td',
            self._html7.format(parse.quote(item_name + '/'),
                               html.escape(item_name + '/')),
            'DIR')
            for item_name in sorted(body[1]))
        resp.extend(self._html2.format(
            'td',
            self._html7.format(parse.quote(item_name),
                               html.escape(item_name)),
            self._size_for_human(size, True))
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
        self._https_redirect(request)
        if request.query_string:
            raise web.HTTPBadRequest
        self._windows_check(request.path)
        path = self._re_pattern.sub('/', request.path)
        if path != request.path:
            raise web.HTTPMovedPermanently(path)
        self._log(request.remote, '->', request.host, request.method,
                  request.path, request.headers.get('Range', ''))
        wpres = self._web_path(path, request.method)
        if callable(wpres):
            return await wpres(request)
        rname, root, ro, to_handle = wpres
        if root is None:
            return self._get_mainpage()
        path = self._local_path_check(root / to_handle, root, True)
        if path.is_dir():
            post_result = ''
            if request.method == 'POST':
                try:
                    post_result = await self._post_handler(request, path, root)
                except web.HTTPException:  # web.HTTPError would also work
                    raise
                except Exception:
                    raise web.HTTPBadRequest
            return self._get_dir(request, rname, path, ro, root, post_result)
        elif path.is_file():
            if request.method != 'GET':
                raise web.HTTPMethodNotAllowed(method, ['GET'])
            return self._get_file(request, path)
        else:
            raise web.HTTPInternalServerError

    def _https_redirect(self, request):
        if self._https and not request.secure:
            new_url = request.url.with_host(self._https[0]).with_scheme(
                                                                    'https')
            if new_url.port != self._https[1]:
                new_url = new_url.with_port(self._https[1])
            raise web.HTTPPermanentRedirect(new_url)

    def _log(self, *content):
        if self._logfile is not None:
            self._logfile.write('{0} - {1}\n'.format(
                time.strftime(self._timef), ' '.join(map(str, content))))

    def change_title(self, title):
        self.page_title = title

    def change_headline(self, headline):
        self.home_page_headline = headline

    def run(self):
        try:
            self._loop.run_until_complete(self.__aenter__())
            self._loop.run_forever()
        except KeyboardInterrupt:
            print()
        finally:
            self._loop.run_until_complete(self.__aexit__())

    def show_ip(self, addr, port, is_ipv6):
        s = None
        dest = addr, port
        try:
            s = socket.socket(socket.AF_INET6 if is_ipv6 else socket.AF_INET,
                              socket.SOCK_DGRAM)
            s.connect(dest)
            ip = s.getsockname()[0]
            self._log('Host IPv6:' if is_ipv6 else 'Host IPv4:', ip)
        except Exception:
            pass
        finally:
            if s is not None:
                s.close()

    async def __aenter__(self):
        if len(self._lpsvr) == 0: # if it is already running, skip
            try:
                for i, j, k in self._listen:
                    runner = web.ServerRunner(web.Server(
                                    self._request_handler, loop=self._loop))
                    await runner.setup()
                    svr = web.TCPSite(runner, i, j, ssl_context=k,
                                      shutdown_timeout=self._wait)
                    await svr.start()
                    self._lpsvr.append(svr)
                    self._log(f'Serving on {i}:{j}' + (' [SSL]' if k else ''))
            except Exception:
                raise ValueError(f'Port {j} already in use.')
            self._log('List of share(s):')
            for name, path in self._fd.items():
                self._log(f'{name}: {path}' +
                          (' [hidden]' if name in self._hd else '') +
                          (' [readonly]' if name in self._ro else ''))
            self.show_ip('8.8.8.8', 53, False)
            self.show_ip('2001:4860:4860::8888', 53, True)

    async def __aexit__(self, exc_type=None, exc_val=None, exc_traceback=None):
        if len(self._lpsvr) > 0: # if no port / no addr to listen on, skip
            self._log(f'Exit in {self._wait} sec(s).')
            svrs = [i.stop() for i in self._lpsvr]
            await asyncio.gather(*svrs, loop=self._loop)
            self._lpsvr.clear()
            self._log('Exiting.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='A simple HTTP file server. '
        'Designed mainly for file sharing via Wi-Fi.',
        epilog='Security not guaranteed. Use it with caution.')
    parser.add_argument(
        'rootdir', nargs='?', help='Root dir of your server. But it could also'
        f' be a file. Default: {pathlib.Path.cwd()}',
        type=pathlib.Path, default='.')
    parser.add_argument(
        '-p', '--port', nargs='?', help='Port to listen on. Default: 8080',
        type=int, default=8080)
    parser.add_argument(
        '-ro', '--readonly', action='store_true', help='Start server under rea'
        'd-only mode. If a file is being shared, this option does nothing.')
    args = parser.parse_args()
    server = Server(listen=(('0.0.0.0', args.port, None), ))
    server.add_share('Shared_Folder', args.rootdir, readonly=args.readonly)
    server.run()
