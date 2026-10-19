package org.imulayout.recorder.core;

import org.junit.Test;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.Assert.*;

public class OperationGateTest {
    @Test public void operationsAreExclusiveAcrossThreadsAndOldReleaseCannotUnlockNewOwner() throws Exception {
        OperationGate gate=new OperationGate();OperationGate.Lease first=gate.tryAcquire();assertNotNull(first);
        AtomicReference<OperationGate.Lease> other=new AtomicReference<>();
        Thread contender=new Thread(()->other.set(gate.tryAcquire()));contender.start();contender.join();assertNull(other.get());
        assertSame(first,gate.find(first.id()));assertNull(gate.find("wrong"));
        first.release();OperationGate.Lease second=gate.tryAcquire();assertNotNull(second);
        first.release();assertTrue(gate.isHeld());assertNull(gate.tryAcquire());
        second.release();assertFalse(gate.isHeld());
    }
}
