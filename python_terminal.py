import os
import shlex
import subprocess
import argparse
import pathlib
import platform
from typing import Tuple, List

# process dependency
try:
    import psutil
except Exception:
    psutil = None

# readline for history      
try:
    import readline
except Exception:
    readline = None

HOME = os.path.expanduser("~")
HISTORY_FILE = os.path.join(HOME, ".pyterminal_history")

# Basic implementation
class PyTerminal:
    def __init__(self):
        self.cwd = os.getcwd()
        self.history: List[str] = []
        self._load_history()
        if readline:
            self._setup_readline()

    #history & readline
    def _load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.history = [line.rstrip("\n") for line in f]
                    if readline:
                        for line in self.history:
                            readline.add_history(line)
        except Exception as e:
            print(f"Warning: could not load history: {e}")

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for entry in self.history[-1000:]:
                    f.write(entry + "\n")
        except Exception as e:
            print(f"Warning: could not save history: {e}")

    def _setup_readline(self):
        try:
            readline.set_history_length(1000)
            BUILTINS = list(self._builtins_map().keys())
            def completer(text, state):
                options = [b for b in BUILTINS if b.startswith(text)]
                try:
                    for name in os.listdir(self.cwd):
                        if name.startswith(text):
                            options.append(name)
                except Exception:
                    pass
                options = sorted(set(options))
                if state < len(options):
                    return options[state]
                return None
            readline.set_completer(completer)
            readline.parse_and_bind('tab: complete')
        except Exception:
            pass

    #commands
    def _builtins_map(self):
        return {
            'ls': self._cmd_ls,
            'cls': self._cmd_cls,
            'pwd': self._cmd_pwd,
            'cd': self._cmd_cd,
            'mkdir': self._cmd_mkdir,
            'rm': self._cmd_rm,
            'rmdir': self._cmd_rmdir,
            'cat': self._cmd_cat,
            'echo': self._cmd_echo,
            'touch': self._cmd_touch,
            'mv': self._cmd_mv,
            'cp': self._cmd_cp,
            'help': self._cmd_help,
            'exit': self._cmd_exit,
            'quit': self._cmd_exit,
            'cpu': self._cmd_cpu,
            'mem': self._cmd_mem,
            'ps': self._cmd_ps,
            'top': self._cmd_top_snapshot,
            'history': self._cmd_history,
            'nlp': self._cmd_nlp, 
        }

    def execute_line(self, line: str) -> Tuple[int, str]:
        """Execute a single line of input. Returns (returncode, output)."""
        if not line.strip():
            return 0, ""
        self.history.append(line)
        parts = [p.strip() for p in shlex.split(line, posix=True) if p.strip()]
        if ';' in line or '&&' in line:
            # split manually by ; and && preserving order
            separators = ['&&', ';']
            cmds = []
            acc = ''
            i = 0
            while i < len(line):
                if line.startswith('&&', i):
                    cmds.append(acc.strip())
                    acc = ''
                    i += 2
                elif line[i] == ';':
                    cmds.append(acc.strip())
                    acc = ''
                    i += 1
                else:
                    acc += line[i]
                    i += 1
            if acc.strip():
                cmds.append(acc.strip())
            last_out = ''
            last_code = 0
            for cmd in cmds:
                last_code, last_out = self.execute_line(cmd)
                if '&&' in line and last_code != 0:
                    break
            return last_code, last_out

        # tokenise
        try:
            tokens = shlex.split(line)
        except Exception as e:
            return 1, f"Error parsing command: {e}"

        if not tokens:
            return 0, ""
        cmd = tokens[0]
        args = tokens[1:]

        builtins = self._builtins_map()
        if cmd in builtins:
            try:
                out = builtins[cmd](args)
                return 0, out
            except TerminalExit as e:
                raise
            except Exception as e:
                return 1, f"Error executing builtin '{cmd}': {e}"
        else:
            return self._execute_external(tokens)

    # implementations
    def _cmd_ls(self, args: List[str]) -> str:
        path = args[0] if args else '.'
        path = self._resolve_path(path)
        try:
            entries = os.listdir(path)
            lines = []
            for name in sorted(entries):
                p = os.path.join(path, name)
                flag = '/' if os.path.isdir(p) else ''
                lines.append(name + flag)
            return '\n'.join(lines)
        except Exception as e:
            return f"ls: {e}"
        
    def _cmd_cls(self, args):
        return self.cwd

    def _cmd_pwd(self, args):
        os.system('cls' if os.name == 'nt' else 'clear')
        return ""

    def _cmd_cd(self, args):
        target = args[0] if args else HOME
        target = self._resolve_path(target)
        if not os.path.isdir(target):
            return f"cd: no such directory: {target}"
        try:
            os.chdir(target)
            self.cwd = os.getcwd()
            return ''
        except Exception as e:
            return f"cd: {e}"

    def _cmd_mkdir(self, args):
        if not args:
            return "mkdir: missing operand"
        out_lines = []
        for d in args:
            p = self._resolve_path(d)
            try:
                os.makedirs(p, exist_ok=False)
                out_lines.append('')
            except FileExistsError:
                out_lines.append(f"mkdir: cannot create directory '{d}': File exists")
            except Exception as e:
                out_lines.append(f"mkdir: {e}")
        return '\n'.join([l for l in out_lines if l])

    def _cmd_rm(self, args):
        if not args:
            return "rm: missing operand"
        out_lines = []
        for target in args:
            p = self._resolve_path(target)
            try:
                if os.path.isdir(p) and not os.path.islink(p):
                    # require -r for directories (naive)
                    out_lines.append(f"rm: cannot remove '{target}': Is a directory")
                else:
                    os.remove(p)
            except FileNotFoundError:
                out_lines.append(f"rm: cannot remove '{target}': No such file or directory")
            except Exception as e:
                out_lines.append(f"rm: {e}")
        return '\n'.join(out_lines)

    def _cmd_rmdir(self, args):
        if not args:
            return "rmdir: missing operand"
        out_lines = []
        for d in args:
            p = self._resolve_path(d)
            try:
                os.rmdir(p)
            except Exception as e:
                out_lines.append(f"rmdir: {e}")
        return '\n'.join(out_lines)

    def _cmd_cat(self, args):
        if not args:
            return "cat: missing operand"
        out = []
        for f in args:
            p = self._resolve_path(f)
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    out.append(fh.read())
            except Exception as e:
                out.append(f"cat: {e}")
        return '\n'.join(out)

    def _cmd_echo(self, args):
        return ' '.join(args)

    def _cmd_touch(self, args):
        if not args:
            return "touch: missing operand"
        for f in args:
            p = self._resolve_path(f)
            try:
                pathlib.Path(p).touch(exist_ok=True)
            except Exception as e:
                return f"touch: {e}"
        return ''

    def _cmd_mv(self, args):
        if len(args) < 2:
            return "mv: missing file operand"
        srcs = args[:-1]
        dst = self._resolve_path(args[-1])
        try:
            if len(srcs) > 1 and not os.path.isdir(dst):
                return "mv: target directory does not exist"
            out_lines = []
            for s in srcs:
                ps = self._resolve_path(s)
                try:
                    if os.path.isdir(dst):
                        final = os.path.join(dst, os.path.basename(ps))
                    else:
                        final = dst
                    os.replace(ps, final)
                except Exception as e:
                    out_lines.append(f"mv: {e}")
            return '\n'.join(out_lines)
        except Exception as e:
            return f"mv: {e}"

    def _cmd_cp(self, args):
        if len(args) < 2:
            return "cp: missing file operand"
        import shutil
        srcs = args[:-1]
        dst = self._resolve_path(args[-1])
        out_lines = []
        try:
            if len(srcs) > 1 and not os.path.isdir(dst):
                return "cp: target directory does not exist"
            for s in srcs:
                ps = self._resolve_path(s)
                try:
                    if os.path.isdir(ps):
                        shutil.copytree(ps, os.path.join(dst, os.path.basename(ps)))
                    else:
                        if os.path.isdir(dst):
                            shutil.copy2(ps, os.path.join(dst, os.path.basename(ps)))
                        else:
                            shutil.copy2(ps, dst)
                except Exception as e:
                    out_lines.append(f"cp: {e}")
            return '\n'.join(out_lines)
        except Exception as e:
            return f"cp: {e}"

    def _cmd_help(self, args):
        builtins = sorted(self._builtins_map().keys())
        lines = ["PyTerminal built-in commands:", ' '.join(builtins), "\nYou can also run system commands."]
        return '\n'.join(lines)

    def _cmd_exit(self, args):
        self._save_history()
        raise TerminalExit()

    def _cmd_history(self, args):
        out = []
        for i, h in enumerate(self.history[-1000:], start=1):
            out.append(f"{i}  {h}")
        return '\n'.join(out)

    # system monitoring
    def _cmd_cpu(self, args):
        if psutil is None:
            return "cpu: psutil not installed. Install with `pip install psutil`"
        return f"CPU percent: {psutil.cpu_percent(interval=0.5)}%\nCores: {psutil.cpu_count(logical=True)}"

    def _cmd_mem(self, args):
        if psutil is None:
            return "mem: psutil not installed. Install with `pip install psutil`"
        vm = psutil.virtual_memory()
        return f"Total: {vm.total} bytes\nAvailable: {vm.available} bytes\nUsed%: {vm.percent}%"

    def _cmd_ps(self, args):
        if psutil is None:
            return "ps: psutil not installed. Install with `pip install psutil`"
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent']):
            try:
                procs.append(p.info)
            except Exception:
                pass
        # sort by cpu
        procs_sorted = sorted(procs, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:20]
        lines = [f"PID\tUSER\tCPU%\tNAME"]
        for p in procs_sorted:
            lines.append(f"{p.get('pid')}\t{p.get('username')}\t{p.get('cpu_percent')}\t{p.get('name')}")
        return '\n'.join(lines)

    def _cmd_top_snapshot(self, args):
        # simple snapshot of top cpu processes + memory
        return self._cmd_ps(args) + "\n\n" + self._cmd_mem(args)

    # ---------- NLP naive translator ----------
    def _cmd_nlp(self, args):
        """
        Use: nlp <natural language command>
        Example: nlp create a folder called test and move file1.txt into it
        This function applies a handful of regex-based translations into shell commands.
        """
        text = ' '.join(args)
        cmd = self.translate_nl_to_cmd(text)
        if not cmd:
            return "Could not interpret natural language command."
        code, out = self.execute_line(cmd)
        return out or f"Executed: {cmd}"

    def translate_nl_to_cmd(self, text: str) -> str:
        # very basic patterns
        text = text.strip().lower()
        import re
        m = re.search(r"create (a )?(folder|directory) called (\w[\w\-_.]*)", text)
        if m:
            name = m.group(3)
            m2 = re.search(r"move (.+) into (?:the )?folder called (\w[\w\-_.]*)|move (.+) into (\w[\w\-_.]*)", text)
            if m2:
                parts = re.findall(r"move ([\w\-_.]+) into", text)
                return f"mkdir {name} && mv {parts[0]} {name}" if parts else f"mkdir {name}"
            return f"mkdir {name}"
        m = re.search(r"move ([\w\-_.]+) to ([\w\-/\.]+)", text)
        if m:
            return f"mv {m.group(1)} {m.group(2)}"
        m = re.search(r"delete (file )?([\w\-_.]+)", text)
        if m:
            return f"rm {m.group(2)}"
        return ''

    # external command execution
    def _execute_external(self, tokens: List[str]) -> Tuple[int, str]:
        try:
            # run without shell for safety; allow piping by the user by using shell explicitly
            proc = subprocess.run(tokens, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = proc.stdout + ("" if not proc.stderr else "\n" + proc.stderr)
            return proc.returncode, out
        except FileNotFoundError:
            return 127, f"{tokens[0]}: command not found"
        except Exception as e:
            return 1, f"Error running external command: {e}"

    # helpers
    def _resolve_path(self, p: str) -> str:
        if p.startswith('~'):
            p = os.path.expanduser(p)
        if not os.path.isabs(p):
            p = os.path.join(self.cwd, p)
        return os.path.normpath(p)


class TerminalExit(Exception):
    pass


# CLI loop 
def repl():
    term = PyTerminal()
    banner = f"PyTerminal (Python backend) - {platform.system()} {platform.release()} - type 'help' for commands"
    print(banner)
    try:
        while True:
            try:
                prompt = f"{os.path.basename(term.cwd)}$ " if term.cwd else '$ '
                if readline:
                    line = input(prompt)
                else:
                    line = input(prompt)
                try:
                    code, out = term.execute_line(line)
                except TerminalExit:
                    print("Exiting PyTerminal. History saved.")
                    break
                if out:
                    print(out)
            except EOFError:
                print('\nReceived EOF. Exiting.')
                break
            except KeyboardInterrupt:
                print('\nKeyboardInterrupt')
    finally:
        term._save_history()

# main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyTerminal - Python-based command terminal')
    repl()
