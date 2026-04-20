# SimObject params for the coherent-witness DMA-pull engine. See
# witness_pull_engine.hh for design notes.

from m5.params import *
from m5.proxy import Parent
from m5.objects.ClockedObject import ClockedObject


class WitnessPullEngine(ClockedObject):
    type = "WitnessPullEngine"
    cxx_header = "dev/witness_pull_engine.hh"
    cxx_class = "gem5::WitnessPullEngine"

    # Port wired to the MESI_Two_Level DMASequencer. Treated as a regular
    # dma port by Ruby (appended to dma_ports in the config).
    dma = RequestPort("DMA port for pulling witness -> writing mirror")

    system = Param.System(Parent.any, "System this engine belongs to")
