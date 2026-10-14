package org.imulayout.recorder.core;
import org.junit.Test;
import static org.junit.Assert.*;

public class WakeLeasePolicyTest {
    static final long S=1_000_000_000L;
    @Test public void renewsWithoutAnIntentionalGap() {
        WakeLeasePolicy p=new WakeLeasePolicy();
        assertNull(p.acquired(0,1,true));
        assertFalse(p.renewDue(19*S));
        assertTrue(p.renewDue(20*S));
        assertNull(p.acquired(20*S,20*S+1,true));
        assertNull(p.check(61*S,true));
    }
    @Test public void rejectsRenewalAcrossThePreviousDeadline() {
        WakeLeasePolicy p=new WakeLeasePolicy();p.acquired(0,1,true);
        assertEquals("wake_lock_coverage_lost",p.acquired(59*S,60*S,true));
    }
    @Test public void resumingAfterExpiryCannotRepairCoverage() {
        WakeLeasePolicy p=new WakeLeasePolicy();p.acquired(0,1,true);
        assertEquals("wake_lock_coverage_lost",p.check(61*S,true));
        assertEquals("wake_lock_coverage_lost",p.acquired(61*S,61*S+1,true));
    }
    @Test public void observedLossIsSticky() {
        WakeLeasePolicy p=new WakeLeasePolicy();p.acquired(0,1,true);
        assertNotNull(p.check(2*S,false));
        assertNotNull(p.check(3*S,true));
    }
    @Test public void initialFailureAndExcessiveAcquireDurationAreRejected() {
        assertNotNull(new WakeLeasePolicy().acquired(0,1,false));
        assertNotNull(new WakeLeasePolicy().acquired(0,60*S,true));
    }
}
