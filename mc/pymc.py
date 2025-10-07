# mc/pymc.py
# -*- coding: utf-8 -*-
import os, sys, importlib.util
from . import _pymc_builtins_ as bi   # uses Can.attach(...) you already added

class Run:
    """
    Lightweight replacement for mc.pymc.Run:
      - does NOT open CAN
      - does NOT upload/compile to device
      - simply imports & runs the MPU .py on host; Sp/Gp go via attached DSA
    """
    def __init__(self, node_id, prg_filename, mpu_filename=None, store=False, start=True, dump=0):
        if getattr(bi.Can, "_dsa", None) is None:
            raise RuntimeError("mc.Can is not attached. Initialize in FlashMPUFile and call Can.attach(dsa, node_id) first.")

        # honor requested node id for Sp/Gp family; no bus reopen
        bi.SpGp_NodeId(int(node_id))
        bi.SpxGpx_NodeId(int(node_id))

        self.node_id      = int(node_id)
        self.prg_filename = prg_filename
        self.mpu_filename = mpu_filename  # ignored in host-run mode
        self.store        = bool(store)   # ignored in host-run mode
        self.start        = bool(start)
        self.dump         = int(dump)

        # resolve file path (relative to CWD or the caller script dir)
        path = os.path.abspath(prg_filename)
        if not os.path.isfile(path):
            caller_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            alt = os.path.join(caller_dir, prg_filename)
            if os.path.isfile(alt):
                path = alt
            else:
                raise FileNotFoundError("MPU program not found: %s" % prg_filename)
        self._path = path

        if self.start:
            self._run()

    def _run(self):
        name = os.path.splitext(os.path.basename(self._path))[0]
        spec = importlib.util.spec_from_file_location(name, self._path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot import MPU program: %s" % self._path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)

        # crude dump compatibility:
        if self.dump & 1:
            # “compiled code” not applicable here; list public symbols instead
            publics = sorted(k for k in mod.__dict__ if not k.startswith("_"))
            print("[DUMP] symbols:", publics)
        if self.dump & 2:
            g = {k: v for k, v in mod.__dict__.items()
                 if not k.startswith("_") and isinstance(v, (int, float, str))}
            print("[DUMP] globals:", g)
