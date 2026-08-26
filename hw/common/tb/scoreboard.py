"""Scoreboard: collects stimulus items on `in_export` and DUT output items on
`out_export`; in check_phase runs `golden(list_of_inputs) -> list_of_expected`
and compares element-wise against the outputs (in order).

Set `golden` via ConfigDB key "golden" or assign `scoreboard.golden` after build.
Default golden is identity (pass-through DUT).
"""
from pyuvm import ConfigDB, uvm_scoreboard, uvm_tlm_analysis_fifo


class Scoreboard(uvm_scoreboard):
    def build_phase(self):
        self.in_fifo = uvm_tlm_analysis_fifo("in_fifo", self)
        self.out_fifo = uvm_tlm_analysis_fifo("out_fifo", self)
        self.in_export = self.in_fifo.analysis_export
        self.out_export = self.out_fifo.analysis_export
        self.golden = ConfigDB().get(self, "", "golden") if ConfigDB().exists(self, "", "golden") else (lambda xs: list(xs))
        self.key = lambda item: item.data
        self.inputs = []
        self.actual = []
        self.errors = 0
        self.passed = False

    def _drain(self, fifo, dst):
        while fifo.can_get():
            ok, item = fifo.try_get()
            if ok:
                dst.append(item)

    def n_actual(self):
        self._drain(self.out_fifo, self.actual)
        return len(self.actual)

    def check_phase(self):
        self._drain(self.in_fifo, self.inputs)
        self._drain(self.out_fifo, self.actual)
        expected = self.golden(self.inputs)
        exp_keys = [self.key(x) if hasattr(x, "data") else x for x in expected]
        act_keys = [self.key(x) for x in self.actual]
        if len(exp_keys) != len(act_keys):
            self.errors += 1
            self.logger.error(f"count mismatch: expected {len(exp_keys)} got {len(act_keys)}")
        for i, (e, a) in enumerate(zip(exp_keys, act_keys)):
            if e != a:
                self.errors += 1
                if self.errors <= 10:
                    self.logger.error(f"item {i}: expected 0x{e:x} got 0x{a:x}")
        self.passed = self.errors == 0
        if self.passed:
            self.logger.info(f"scoreboard PASS: {len(act_keys)} items matched")
        else:
            self.logger.error(f"scoreboard FAIL: {self.errors} errors")

    def report_phase(self):
        assert self.passed, f"scoreboard: {self.errors} mismatches"
