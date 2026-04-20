/* See witness_pull_engine.hh for the design rationale. */
#include "dev/witness_pull_engine.hh"

#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/DMA.hh"
#include "mem/packet_access.hh"
#include "sim/system.hh"

namespace gem5
{

WitnessPullEngine *WitnessPullEngine::instance = nullptr;

WitnessPullEngine::WitnessPullEngine(const Params &p)
    : ClockedObject(p),
      dmaPort(this, p.system),
      sys(p.system),
      tickEvent([this]{ onTick(); }, name() + ".tick", false),
      readDoneEvent([this]{ onReadDone(); }, name() + ".readDone", false),
      writeDoneEvent([this]{ onWriteDone(); }, name() + ".writeDone", false),
      stats(this)
{
    if (instance != nullptr) {
        fatal("WitnessPullEngine: more than one instance is not supported "
              "(pseudo_inst dispatch uses a singleton lookup).");
    }
    instance = this;
}

Port &
WitnessPullEngine::getPort(const std::string &if_name, PortID idx)
{
    if (if_name == "dma") return dmaPort;
    return ClockedObject::getPort(if_name, idx);
}

void
WitnessPullEngine::configure(Addr src_paddr, Addr dst_paddr,
                             uint64_t size, uint64_t period_ticks)
{
    /* Refuse reconfiguration while a pull is in flight — the buffer
     * would be torn. The bench is expected to call configure() once
     * at startup before start(). */
    if (inFlight) {
        warn("WitnessPullEngine::configure ignored: pull in flight");
        return;
    }
    if (size == 0) {
        warn("WitnessPullEngine::configure ignored: size=0");
        return;
    }
    srcPaddr = src_paddr;
    dstPaddr = dst_paddr;
    regionSize = size;
    period = period_ticks ? period_ticks : clockPeriod();
    buffer.assign(size, 0);
    configured = true;
    DPRINTF(DMA, "WitnessPullEngine: configured src=%#x dst=%#x "
                 "size=%llu period=%llu\n",
            src_paddr, dst_paddr,
            (unsigned long long)size, (unsigned long long)period);
}

void
WitnessPullEngine::startPulling()
{
    if (!configured) {
        warn("WitnessPullEngine::start ignored: not configured");
        return;
    }
    if (running) return;
    running = true;
    if (!tickEvent.scheduled()) {
        schedule(tickEvent, curTick() + period);
    }
}

void
WitnessPullEngine::stopPulling()
{
    running = false;
    if (tickEvent.scheduled()) deschedule(tickEvent);
}

void
WitnessPullEngine::onTick()
{
    if (!running) return;
    ++stats.ticks;

    if (inFlight) {
        /* Previous pull is still draining; skip this tick. */
        ++stats.skippedBusy;
    } else {
        inFlight = true;
        /* Coherent read from witness region. */
        dmaPort.dmaAction(MemCmd::ReadReq, srcPaddr, regionSize,
                          &readDoneEvent, buffer.data(), 0);
    }

    schedule(tickEvent, curTick() + period);
}

void
WitnessPullEngine::onReadDone()
{
    /* Immediately turn the pulled bytes into a DMA write to the mirror. */
    dmaPort.dmaAction(MemCmd::WriteReq, dstPaddr, regionSize,
                      &writeDoneEvent, buffer.data(), 0);
}

void
WitnessPullEngine::onWriteDone()
{
    ++stats.pullsCompleted;
    stats.bytesTransferred += regionSize;
    inFlight = false;
}

WitnessPullEngine::Stats::Stats(statistics::Group *parent)
    : statistics::Group(parent),
      ADD_STAT(ticks, "Number of pull ticks that fired"),
      ADD_STAT(pullsCompleted, "Pulls that completed read+write"),
      ADD_STAT(bytesTransferred,
               "Total bytes transferred (src->dst)"),
      ADD_STAT(skippedBusy,
               "Ticks skipped because the previous pull was still in flight")
{ }

} // namespace gem5
