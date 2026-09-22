"""Child-process-only fake Selenium, including a detached browser descendant."""
from pathlib import Path
import runpy
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

mode = sys.argv.pop(1)
pid_record = sys.argv.pop(1)
profile = sys.argv[2]
modules = {name: ModuleType(name) for name in ('selenium','selenium.webdriver','selenium.webdriver.chrome','selenium.webdriver.chrome.options')}

class FakeChrome:
    def __init__(self, **_):
        # Model ChromeDriver -> detached Chrome/crashpad. In the success case
        # the service exits BEFORE cleanup, forcing subreaper adoption.
        spawn_tree = """
import os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
Path(sys.argv[1]).write_text(str(os.getpid()) + '\\n' + str(child.pid))
if sys.argv[2] != 'success': time.sleep(60)
"""
        self.child = subprocess.Popen([sys.executable, '-c', spawn_tree, pid_record, mode], start_new_session=True)
        self.service = SimpleNamespace(process=self.child)
        limit = time.monotonic() + 1
        while not Path(pid_record).exists() and time.monotonic() < limit:
            time.sleep(.01)
        if mode == 'success': self.child.wait(timeout=1)
        if mode == 'partial': raise ValueError('partial constructor')
        if mode == 'creation_hang': time.sleep(60)
    def set_page_load_timeout(self, _): pass
    def set_script_timeout(self, _): pass
    def get(self, _):
        if mode == 'navigation': raise ValueError('navigation')
        if mode == 'overall': time.sleep(60)
    def quit(self):
        with open(pid_record + '.quit', 'a') as out: out.write('quit\n')
        if mode == 'quit_hang': time.sleep(60)
        if mode == 'quit': raise ValueError('quit')
        # Deliberately leave the detached child; lifecycle must reap it.

modules['selenium'].webdriver = modules['selenium.webdriver']
modules['selenium.webdriver'].Chrome = FakeChrome
modules['selenium.webdriver.chrome.options'].Options = lambda:SimpleNamespace(add_argument=lambda _:None)
sys.modules.update(modules)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
runpy.run_module('app.research.browser_lifecycle',run_name='__main__')
