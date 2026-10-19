package org.imulayout.recorder.core;
import org.junit.Test;
import java.util.ArrayList;
import java.util.List;
import static org.junit.Assert.*;
public class SessionControllerTest {
    @Test public void concurrentStopPathsUnregisterOnlyOnce() {
        List<String> stops=new ArrayList<>();
        SessionController c=new SessionController(s->true,stops::add);
        c.start(100);c.start(200);
        assertEquals(100,c.startNs);
        c.requestStop("user",300);c.requestStop("notification",301);
        assertEquals(List.of("user"),stops);
        assertFalse(c.onSensorSample(0,302,302,0,0,9.8f,3));
    }
    @Test public void overflowCountsTheRejectedSampleAndClosesTheGate() {
        List<String> stops=new ArrayList<>();
        SessionController c=new SessionController(s->false,stops::add);c.start(100);
        assertFalse(c.onSensorSample(0,101,102,0,0,0,0));
        assertEquals(1,c.received[0]);assertEquals(1,c.dropped[0]);
        assertEquals(List.of("queue_overflow"),stops);
    }
    @Test public void maxDurationIsNormalButDrainTimeoutIsNot() {
        SessionController c=new SessionController(s->true,s->{});c.start(10);
        c.tick(10+RecordingContract.MAX_DURATION_NS);
        assertEquals("max_duration",c.stoppedReason);assertFalse(c.abnormal);
        c.tick(c.stopNs+RecordingContract.DRAIN_TIMEOUT_NS);
        assertTrue(c.abnormal);assertEquals("drain_timeout",c.stopFailure);
        assertFalse(c.closed);
    }
    @Test public void simultaneousStopRequestsShareOneDrain() throws Exception {
        java.util.concurrent.atomic.AtomicInteger calls=new java.util.concurrent.atomic.AtomicInteger();
        SessionController c=new SessionController(s->true,s->calls.incrementAndGet());c.start(1);
        java.util.concurrent.CountDownLatch ready=new java.util.concurrent.CountDownLatch(1);
        Runnable request=()->{try{ready.await();c.requestStop("user",2);}catch(InterruptedException e){Thread.currentThread().interrupt();}};
        Thread a=new Thread(request),b=new Thread(request);a.start();b.start();ready.countDown();a.join(1000);b.join(1000);
        assertFalse(a.isAlive());assertFalse(b.isAlive());assertEquals(1,calls.get());
    }
}
