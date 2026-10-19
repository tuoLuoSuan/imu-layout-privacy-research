package org.imulayout.recorder.core;
public final class WakeLeasePolicy {
    private long deadline,lastAcquire;
    private boolean started,failed;
    public synchronized String acquired(long before,long after,boolean held) {
        if(failed || !held || after<before || after-before>=60_000_000_000L
                || (started && (before>=deadline || after>=deadline))) {
            failed=true;return "wake_lock_coverage_lost";
        }
        started=true;lastAcquire=before;deadline=before+60_000_000_000L;return null;
    }
    public synchronized String check(long now,boolean held) {
        if(failed || !started || !held || now>=deadline || now<lastAcquire) {
            failed=true;return "wake_lock_coverage_lost";
        }
        return null;
    }
    public synchronized boolean renewDue(long now) {
        return started && !failed && now-lastAcquire>=20_000_000_000L;
    }
    public synchronized long deadline() {return deadline;}
}
