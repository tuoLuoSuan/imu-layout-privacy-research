package org.imulayout.recorder.core;
import org.junit.Test;
import java.util.List;
import static org.junit.Assert.*;

public class ClockMappingTest {
    static final long S=1_000_000_000L;
    @Test public void neverBridgesAbsentAnchorsOrExtrapolates() {
        ClockMapping.Result r=ClockMapping.build(List.of(
            new ClockMapping.Anchor(1*S,1000,1*S+2),
            new ClockMapping.Anchor(11*S,11000,11*S+2),
            new ClockMapping.Anchor(31*S,31000,31*S+2)),0,40*S);
        assertEquals(1,r.mapped.size());
        assertEquals(2,r.unmapped.size());
        assertEquals(1*S+1,r.mapped.get(0).start);
        assertEquals(11*S+1,r.mapped.get(0).end);
    }
    @Test public void rejectsWideOrNonIncreasingReads() {
        assertFalse(new ClockMapping.Anchor(1,0,1).valid());
        assertFalse(new ClockMapping.Anchor(10,0,9).valid());
        assertFalse(new ClockMapping.Anchor(1,0,6_000_001).valid());
        assertTrue(new ClockMapping.Anchor(1,0,5_000_001).valid());
    }
    @Test public void wallClockJumpDoesNotCreateMapping() {
        ClockMapping.Result r=ClockMapping.build(List.of(
            new ClockMapping.Anchor(0,1000,2),
            new ClockMapping.Anchor(10*S,11101,10*S+2)),0,11*S);
        assertEquals(0,r.mapped.size());assertEquals(1,r.unmapped.size());
    }
    @Test public void exactMappingBoundariesAreAccepted() {
        assertEquals(1,ClockMapping.build(List.of(new ClockMapping.Anchor(0,0,2),
            new ClockMapping.Anchor(15*S,15100,15*S+2)),0,16*S).mapped.size());
    }
    @Test public void invalidIntermediateAnchorIsNotSilentlyRemoved() {
        assertEquals(0,ClockMapping.build(List.of(new ClockMapping.Anchor(0,0,2),
            new ClockMapping.Anchor(5*S,5000,5*S+6_000_000),new ClockMapping.Anchor(10*S,10000,10*S+2)),0,11*S).mapped.size());
    }
}
