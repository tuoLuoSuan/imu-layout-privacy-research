package org.imulayout.recorder.core;
import java.util.function.Consumer;
import java.util.function.Predicate;
import static org.imulayout.recorder.core.RecordingContract.*;
public final class SessionController {
    public volatile long startNs,stopNs;
    public volatile boolean started,stopping,closed,abnormal;
    public volatile String stoppedReason="",stopFailure="";
    public final long[] received={0,0},enqueued={0,0},dropped={0,0};
    public long outsideGate;
    private final Predicate<Sample> offer;
    private final Consumer<String> stop;
    public SessionController(Predicate<Sample> offer,Consumer<String> stop) {this.offer=offer;this.stop=stop;}
    public synchronized void start(long now) {if(!started){startNs=now;started=true;}}
    public synchronized boolean onSensorSample(int channel,long eventNs,long receivedNs,float x,float y,float z,int accuracy) {
        tick(receivedNs);
        if(!started || stopping || eventNs<startNs || eventNs>=startNs+MAX_DURATION_NS) {outsideGate++;return false;}
        long seq=++received[channel];
        if(offer.test(new Sample(channel,seq,eventNs,receivedNs,x,y,z,accuracy))) {
            enqueued[channel]++;return true;
        }
        dropped[channel]++;requestStop("queue_overflow",receivedNs);return false;
    }
    public synchronized void requestStop(String reason,long now) {
        if(stopping || closed)return;
        stopping=true;stopNs=now;stoppedReason=reason;
        abnormal=!reason.equals("user") && !reason.equals("notification") && !reason.equals("max_duration") && !reason.equals("joint_probe_complete");
        stop.accept(reason);
    }
    public synchronized void tick(long now) {
        if(started && !stopping && now-startNs>=MAX_DURATION_NS)requestStop("max_duration",now);
        if(stopping && !closed && now-stopNs>=DRAIN_TIMEOUT_NS) {abnormal=true;stopFailure="drain_timeout";}
    }
    public synchronized void finish(boolean success) {closed=true;if(!success)abnormal=true;}
}
