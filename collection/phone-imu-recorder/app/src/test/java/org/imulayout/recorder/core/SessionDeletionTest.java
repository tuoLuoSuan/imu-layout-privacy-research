package org.imulayout.recorder.core;

import org.imulayout.recorder.SessionExporter;
import org.junit.Test;
import org.junit.Assume;
import java.io.*;
import java.nio.file.*;
import java.util.UUID;
import static org.junit.Assert.*;

public class SessionDeletionTest {
    private Path app() throws Exception{return Files.createTempDirectory("imu-delete-synthetic-").toRealPath();}
    private Path record(Path app,boolean sealed) throws Exception {
        Path dir=Files.createDirectories(app.resolve("sessions").resolve(UUID.randomUUID().toString()));
        Files.writeString(dir.resolve("accelerometer.csv"),"synthetic only");
        if(sealed)Files.writeString(dir.resolve("manifest.json"),"{}");return dir;
    }
    @Test public void deletesOnlyChosenSessionAndKeepsNeighborAndExport() throws Exception {
        Path app=app(),a=record(app,true),b=record(app,true),zip=app.resolve("exported.zip");Files.writeString(zip,"external synthetic archive");
        SessionDeletion store=new SessionDeletion(app.toFile());
        assertTrue(Files.exists(a)); // Merely constructing or cancelling performs no deletion.
        store.delete(a.getFileName().toString());
        assertFalse(Files.exists(a));assertTrue(Files.exists(b.resolve("accelerometer.csv")));
        assertEquals("external synthetic archive",Files.readString(zip));assertEquals(0,store.retryPending());
    }
    @Test public void refusesUnsealedSessionsAndInvalidIds() throws Exception {
        Path app=app(),a=record(app,false);SessionDeletion store=new SessionDeletion(app.toFile());
        for(String id:new String[]{a.getFileName().toString(),"../outside","/outside","not-a-uuid",""}) {
            try{store.delete(id);fail(id);}catch(IOException expected){}
        }
        assertTrue(Files.exists(a.resolve("accelerometer.csv")));
    }
    @Test public void interruptedCleanupCannotBeRecoveredAsExperimentAndCanBeRetried() throws Exception {
        Path app=app(),a=record(app,true);
        SessionDeletion store=new SessionDeletion(app.toFile(),dir->{throw new IOException("synthetic disk failure");});
        try{store.delete(a.getFileName().toString());fail();}catch(IOException expected){assertTrue(expected.getMessage().contains("尚未清理"));}
        assertFalse(Files.exists(a));Path pending=app.resolve("pending-session-deletions").resolve(a.getFileName());
        assertTrue(Files.exists(pending));SessionExporter.recover(app.resolve("sessions").toFile());
        assertFalse(Files.exists(pending.resolve("metadata.json")));
        assertEquals(1,new SessionDeletion(app.toFile()).retryPending());assertFalse(Files.exists(pending));
    }
    @Test public void refusesLinkedRootSessionAndNestedFilesWithoutTouchingTarget() throws Exception {
        Path app=app(),outside=app(),a=record(app,true);
        Path link=a.resolve("linked");
        try{Files.createSymbolicLink(link,outside);}catch(IOException|UnsupportedOperationException|SecurityException e){Assume.assumeNoException(e);}
        SessionDeletion store=new SessionDeletion(app.toFile());
        try{store.delete(a.getFileName().toString());fail();}catch(IOException expected){}
        assertTrue(Files.exists(a.resolve("accelerometer.csv")));assertTrue(Files.isDirectory(outside));
        Path linkedSession=app.resolve("sessions").resolve(UUID.randomUUID().toString());Files.createSymbolicLink(linkedSession,outside);
        try{store.delete(linkedSession.getFileName().toString());fail();}catch(IOException expected){}
        Path app2=app();Files.createSymbolicLink(app2.resolve("sessions"),outside);
        try{new SessionDeletion(app2.toFile()).retryPending();fail();}catch(IOException expected){}
        assertTrue(Files.isDirectory(outside));
    }
}
