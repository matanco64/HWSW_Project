"""BaseEnv: uvm_env with a scoreboard slot; subclasses add agents in build_phase
and wire monitor analysis ports to the scoreboard in connect_phase."""
from pyuvm import uvm_env


class BaseEnv(uvm_env):
    def build_phase(self):
        self.scoreboard = None

    def connect_phase(self):
        pass
