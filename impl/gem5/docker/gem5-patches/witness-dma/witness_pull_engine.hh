/*
 * WitnessPullEngine: a minimal DMA-pull device for the coherent-witness
 * gem5 study. Periodically issues a coherent DMA read from src_paddr
 * into a scratch buffer and, on completion, issues a DMA write of the
 * same bytes to dst_paddr. Both are routed through Ruby's DMASequencer,
 * so the monitor reading dst_paddr sees only invalidations from THIS
 * engine, never from the producer thread — that is the baseline-C
 * comparison point.
 *
 * Configuration happens via two pseudo-instructions hijacked from the
 * M5OP_RESERVED slots (see pseudo_inst.hh): m5_dma_setup() passes the
 * producer-side and monitor-side virtual addresses plus region size
 * and period, and m5_dma_start() arms the periodic tick.
 *
 * This is intentionally not derived from DmaDevice / PioDevice: DmaDevice
 * extends PioDevice, which requires MMIO registers — impossible to reach
 * from gem5 SE-mode user code. Instead we own a DmaPort directly, the
 * same way DmaVirtDevice siblings do internally, and drive it from an
 * event scheduled in our own clock domain.
 */
#ifndef __DEV_WITNESS_PULL_ENGINE_HH__
#define __DEV_WITNESS_PULL_ENGINE_HH__

#include <vector>

#include "base/statistics.hh"
#include "base/types.hh"
#include "dev/dma_device.hh"
#include "params/WitnessPullEngine.hh"
#include "sim/clocked_object.hh"

namespace gem5
{

class System;

class WitnessPullEngine : public ClockedObject
{
  public:
    PARAMS(WitnessPullEngine);
    explicit WitnessPullEngine(const Params &p);

    Port &getPort(const std::string &if_name,
                  PortID idx = InvalidPortID) override;

    /* Called from the pseudo_inst handlers. */
    void configure(Addr src_paddr, Addr dst_paddr,
                   uint64_t size, uint64_t period_ticks);
    void startPulling();
    void stopPulling();

    bool isConfigured() const { return configured; }

    /* The pseudo_inst dispatch looks the engine up through this static
     * pointer. The first WitnessPullEngine constructed registers itself;
     * multiple engines in one simulation are a configuration error. */
    static WitnessPullEngine *instance;

  private:
    DmaPort dmaPort;
    System *sys;

    EventFunctionWrapper tickEvent;
    EventFunctionWrapper readDoneEvent;
    EventFunctionWrapper writeDoneEvent;

    Addr srcPaddr = 0;
    Addr dstPaddr = 0;
    uint64_t regionSize = 0;
    Tick period = 0;
    std::vector<uint8_t> buffer;
    bool configured = false;
    bool running = false;
    bool inFlight = false;

    struct Stats : public statistics::Group
    {
        explicit Stats(statistics::Group *parent);
        statistics::Scalar ticks;
        statistics::Scalar pullsCompleted;
        statistics::Scalar bytesTransferred;
        statistics::Scalar skippedBusy;
    } stats;

    void onTick();
    void onReadDone();
    void onWriteDone();
};

} // namespace gem5

#endif // __DEV_WITNESS_PULL_ENGINE_HH__
