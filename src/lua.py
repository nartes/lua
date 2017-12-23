import io
import sys
import os
import json
import optparse
import pprint
import tempfile
import subprocess


class Utils:
    def sub_shell(cmds,
                  communicate=False,
                  stderr_to_stdout=False,
                  verbose=False,
                  wait=True,
                  env=dict(list(os.environ.items())),
                  critical=True):
        ret = None

        if verbose:
            print('*' * 9 + 'BEGIN_COMAND' + '*' * 9)
            print(cmds)
            print('*' * 9 + 'END_COMAND' + '*' * 9)

        tf = tempfile.mktemp()
        f = io.open(tf, 'w')
        f.write(u'' + cmds)
        f.close()

        _env = dict([(k.upper(), str(v)) for (k, v) in env.items()])

        if communicate:
            inp = subprocess.PIPE
            outp = subprocess.PIPE
            if stderr_to_stdout:
                errp = outp
            else:
                errp = subprocess.PIPE

            proc = subprocess.Popen(['zsh', tf],
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    env=_env)
            try:
                proc.wait()
                out, err = proc.communicate()
                ret = out.decode()
            except:
                proc.kill()
        else:
            proc = subprocess.Popen(['zsh', tf],
                                    stdin=sys.stdin,
                                    stdout=sys.stdout,
                                    stderr=sys.stderr,
                                    env=_env)
            try:
                if wait:
                    proc.wait()
            except:
                proc.kill()

        if wait:
            if proc.returncode != 0 and critical:
                raise ValueError(proc.returncode)

        return ret


class Lua:
    def __init__(self, args):
        parser = optparse.OptionParser()
        parser.add_option("-t", "--task", dest="task",
                          help="a name of the main task")
        parser.add_option("--env", dest="env", default=json.dumps({}),
                          help="additional environmental variables as a json string")
        parser.add_option("-V", "--verbose", dest="verbose", action="store_true", default=False,
                          help="enable the verbose mode")

        self._options, self._args = parser.parse_args(args)

        self._initial_args = args

        self.setup()

        if self._options.task in ['custom_prefix', 'clean', 'build', 'install', 'environment']:
            getattr(self, self._options.task)()
        else:
            raise ValueError('Unknown command %s' % ' '.join(args))

    def setup(self):
        self._env = {}

        self._env.update(dict([
            (k.lower(), v) for (k, v) in json.loads(self._options.env).items()
        ]))

        self._env['project_root'] = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..'))

        prefix = self._env.get('prefix', 'lua_default')
        if not os.path.isabs(prefix):
            prefix = os.path.join(self._env['project_root'], 'tmp', 'install', prefix)
        self._env['prefix'] = prefix

        self._env['ver'] = self._env.get('ver', '5.3')
        self._env['rel'] = self._env.get('rel', '4')

        self._env['pkgname'] = self._env.get('pkgname', 'lua')

    def _sub_shell(self, cmds, env={}, *args, **kwargs):
        return Utils.sub_shell(
            cmds=cmds,
            env=dict([
                (k.lower(), v) for (k, v) in
                list(os.environ.items()) +
                list(self._env.items()) +
                list(env.items())
            ]),
            verbose=self._options.verbose,
            *args,
            **kwargs
        )

    def clean(self):
        self._sub_shell(r"""
            cd $PROJECT_ROOT;
            git clean -xdf -e tmp -e tags -e .clang-format
            """
                        )

    def build(self):
        self._sub_shell(r"""
            cd $PROJECT_ROOT;
            make -C src -j3 V=$VER R=$REL MYCFLAGS="$CFLAGS"\
                MYLDFLAGS="$LDFLAGS" linux;
            """
                        )

    def install(self):
        self._sub_shell(r"""
            cd $PROJECT_ROOT;
            mkdir -p build;
            """
                        )

        with io.open(os.path.join(self._env['project_root'], 'src', 'lua.pc'), 'r') as inf:
            with io.open(os.path.join(self._env['project_root'], 'build', 'lua.pc'), 'w') as outf:
                outf.write(
                    inf.read()\
                        .replace('%VER%', self._env['ver'])\
                        .replace('%REL%', self._env['rel'])\
                        .replace('%PREFIX%', self._env['prefix'])
                )

        self._sub_shell(r"""
            cd $PROJECT_ROOT;
            mkdir -p build;
            mkdir -p tmp/install;
            install -D build/lua.pc $PREFIX/lib/pkgconfig/$PKGNAME.pc;
            make -f Makefile V=$VER R=$REL install INSTALL_TOP=$PREFIX\
                TO_LIB="liblua.a liblua.so liblua.so.$VER";
            """
                        )

    def environment(self):
        print(json.dumps({
            'pkg_config_path': os.path.join(self._env['prefix'], 'lib', 'pkgconfig'),
            'ld_library_path': os.path.join(self._env['prefix'], 'lib'),
            'pkgname': self._env['pkgname']
        }))

    def custom_prefix(self):
        self.clean()
        self.build()
        self.install()


if __name__ == '__main__':
    Lua(sys.argv[1:])
