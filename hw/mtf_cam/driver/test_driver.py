"""Driver-model tests (stage 10). Standalone, no simulator:

  python3 hw/mtf_cam/driver/test_driver.py

1. Every register constant matches MAS §4 AND rtl/mtf_regs.sv (check_regmap -> 0 differences).
2. The API drives a full expand_block() invocation on the ModelBus (through the frozen golden
   predictor golden/list_model.py): L-vector, BYTES_OUT, SYMBOLS_IN, MAX_RUN, CYCLES, DONE-then-W1C.
3. Error paths: ERR_PARAM (N_USED = 0) rejects the doorbell; ERR_BUSY (config write while BUSY).

This is the driver-MODEL test (distinct from the cocotb directed `test_driver` in tb/, which drives
the RTL). The RTL-cosim of this same driver is tb/test_driver_model.py (SimBackend, `make sim
MODULE=test_driver_model`).
"""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "golden"))   # golden/list_model.py

import check_regmap  # noqa: E402
from mtf_cam_driver import (  # noqa: E402
    MtfDriver, ModelBus, ID, ID_VALUE, CAPS,
    ST_DONE, ST_ERR_PARAM, ST_ERR_BUSY, ST_BUSY,
    CTRL, CTRL_DOORBELL, SYMBOL_LIMIT, BYTES_LIMIT, USED_BASE,
)

# test_smoke block (env.py SMOKE_*): used {65,66,67,68}, stream RUNA,RUNA,MTF2,MTF3,MTF2,EOB.
SMOKE_USED = [65, 66, 67, 68]
SMOKE_SYMS = [0, 0, 2, 3, 2, 5]                 # EOB value = N_USED + 1 = 5
SMOKE_LVEC = bytes([65, 65, 65, 66, 67, 66])    # expected L-vector (env comment)


def test_regmap():
    assert check_regmap.main() == 0, "check_regmap reported differences"


def test_id_and_caps():
    async def go():
        bus = ModelBus(W=8, D=8, N_LIST=256)
        assert await bus.read32(ID) == ID_VALUE
        caps = await bus.read32(CAPS)
        assert caps == 0x0100_0808, f"CAPS 0x{caps:08x} != 0x01000808 (W=8,D=8,N_LIST=256)"
    asyncio.run(go())


def test_full_expand():
    async def go():
        bus = ModelBus(W=8, D=8)
        d = MtfDriver(bus)
        c = await d.expand_block(SMOKE_SYMS, SMOKE_USED)
        assert c["l_bytes"] == SMOKE_LVEC, (c["l_bytes"], SMOKE_LVEC)
        assert c["bytes_out"] == 6, c
        assert c["symbols_in"] == 6, c
        assert c["max_run"] == 3, c
        assert c["init_cycles"] == 4, c            # N_USED
        assert c["cycles"] > 0, c
        assert c["status"] & ST_DONE, c
        # expand_block clears DONE (W1C) at the end
        assert not (await d.status() & ST_DONE)
        return c["cycles"]
    return asyncio.run(go())


def test_err_param():
    async def go():
        bus = ModelBus()
        d = MtfDriver(bus)
        # program limits but leave the used map empty -> N_USED = 0 -> doorbell rejected (F9)
        await bus.write32(SYMBOL_LIMIT, 1 << 20)
        await bus.write32(BYTES_LIMIT, 1 << 20)
        await bus.write32(CTRL, CTRL_DOORBELL)
        s = await d.status()
        assert s & ST_ERR_PARAM, f"STATUS 0x{s:04x} lacks ERR_PARAM"
        assert not (s & ST_BUSY), "ERR_PARAM must not raise BUSY"
    asyncio.run(go())


def test_err_busy():
    async def go():
        bus = ModelBus(W=8, D=8)
        d = MtfDriver(bus)
        await d.configure(SMOKE_USED)
        # force BUSY (bypass the model's instant-complete) then attempt a config write
        bus.busy = True
        await bus.write32(SYMBOL_LIMIT, 1234)      # config write while BUSY
        assert bus.sticky & ST_ERR_BUSY, "config write while BUSY must set ERR_BUSY"
        await bus.write32(CTRL, CTRL_DOORBELL)     # doorbell while BUSY
        assert bus.sticky & ST_ERR_BUSY
    asyncio.run(go())


def main():
    tests = [test_regmap, test_id_and_caps, test_full_expand, test_err_param, test_err_busy]
    for t in tests:
        r = t()
        extra = f" (cycles={r})" if r else ""
        print(f"PASS {t.__name__}{extra}")
    print(f"\nALL {len(tests)} DRIVER-MODEL TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
