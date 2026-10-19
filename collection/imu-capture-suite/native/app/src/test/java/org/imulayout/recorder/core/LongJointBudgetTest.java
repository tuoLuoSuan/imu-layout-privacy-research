package org.imulayout.recorder.core;
import org.junit.Test;
import static org.junit.Assert.*;
public class LongJointBudgetTest {
 @Test public void tenMinuteCollectionAndUploadReserveDoNotHitOldThreeMinuteStop(){
  SessionController c=new SessionController(s->true,r->{});c.start(1);
  c.tick(600_000_000_001L);assertFalse(c.stopping);
  c.tick(1_020_000_000_001L);assertFalse(c.stopping);
  c.tick(1+RecordingContract.MAX_DURATION_NS);assertTrue(c.stopping);assertEquals("max_duration",c.stoppedReason);
 }
}
