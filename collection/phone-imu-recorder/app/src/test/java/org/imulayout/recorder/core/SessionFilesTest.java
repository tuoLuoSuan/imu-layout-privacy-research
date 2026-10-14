package org.imulayout.recorder.core;
import org.junit.Test;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.Assert.*;
public class SessionFilesTest {
    @Test public void stopDrainsEveryAcceptedSample() throws Exception {
        Path dir=Files.createTempDirectory("imu-synthetic-");
        AtomicLong clock=new AtomicLong(10);
        SessionFiles f=new SessionFiles(dir.toFile(),clock::get,s->{});
        f.start();
        for(int i=1;i<=100;i++)assertTrue(f.offer(new RecordingContract.Sample(0,i,i,i,1,2,3,0)));
        f.requestClose();f.worker.join(3000);
        assertTrue(f.finished);assertNull(f.error);
        assertEquals(100,f.written[0]);assertEquals(100,f.confirmed[0]);
        assertEquals(101,Files.readAllLines(dir.resolve("accelerometer.csv")).size());
    }
    @Test public void fullQueueRefusesWithoutBlocking() throws Exception {
        SessionFiles f=new SessionFiles(Files.createTempDirectory("imu-synthetic-").toFile(),()->1L,s->{});
        for(int i=0;i<4096;i++)assertTrue(f.offer(new RecordingContract.Sample(0,i,1,1,0,0,0,0)));
        assertFalse(f.offer(new RecordingContract.Sample(0,4097,1,1,0,0,0,0)));
    }
    @Test public void flushPolicyHasByteAndDirtyTimeTriggers() {
        assertFalse(SessionFiles.shouldFlush(0,6_000_000_000L));
        assertTrue(SessionFiles.shouldFlush(1,5_000_000_000L));
        assertTrue(SessionFiles.shouldFlush(65536,1));
        assertFalse(SessionFiles.shouldFlush(65535,4_999_999_999L));
    }
    @Test public void storageOpenFailureIsReportedInsteadOfSaved() throws Exception {
        java.util.List<String> errors=new java.util.concurrent.CopyOnWriteArrayList<>();
        SessionFiles f=new SessionFiles(Files.createTempFile("imu-synthetic-block-",".tmp").toFile(),()->1L,errors::add);
        f.start();f.worker.join(3000);
        assertTrue(f.finished);assertNotNull(f.error);assertEquals(java.util.List.of("storage_failure"),errors);
    }
}
