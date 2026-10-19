package org.imulayout.recorder.core;
import org.imulayout.recorder.SessionExporter;
import org.junit.Test;
import java.io.*;
import java.nio.file.*;
import org.json.*;
import static org.junit.Assert.*;
public class SessionExporterTest {
    @Test public void manifestExcludesItselfAndExportsAreImmutable() throws Exception {
        File dir=Files.createTempDirectory("imu-synthetic-export-").toFile();
        Files.writeString(new File(dir,"evidence.txt").toPath(),"synthetic fixture");
        SessionExporter.seal(dir,Jsons.object("completion_state","aborted"));
        assertTrue(new File(dir,"manifest.json").exists());
        String digest=Jsons.sha256(new File(dir,"manifest.json"));
        JSONArray files=Jsons.read(new File(dir,"manifest.json")).getJSONArray("files");
        for(int i=0;i<files.length();i++)assertNotEquals("manifest.json",files.getJSONObject(i).getString("path"));
        SessionExporter.zip(dir,new ByteArrayOutputStream());SessionExporter.zip(dir,new ByteArrayOutputStream());
        assertEquals(digest,Jsons.sha256(new File(dir,"manifest.json")));
    }
    @Test public void refusesToExportChangedSource() throws Exception {
        File dir=Files.createTempDirectory("imu-synthetic-export-").toFile();
        File source=new File(dir,"evidence.txt");Files.writeString(source.toPath(),"synthetic fixture");
        SessionExporter.seal(dir,Jsons.object("completion_state","aborted"));Files.writeString(source.toPath(),"changed");
        try {SessionExporter.zip(dir,new ByteArrayOutputStream());fail("tampered source was exported");}catch(IOException expected){}
    }
    @Test public void recoveryPreservesPartialRawFilesAndNeverClaimsCompletion() throws Exception {
        File root=Files.createTempDirectory("imu-synthetic-recovery-").toFile();File dir=new File(root,"interrupted");assertTrue(dir.mkdir());
        File raw=new File(dir,"accelerometer.csv");Files.writeString(raw.toPath(),"sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy\n1,100,101,102,0,0,9.8,3\n2,partial");
        String original=Jsons.sha256(raw);SessionExporter.recover(root);
        assertEquals(original,Jsons.sha256(raw));
        assertEquals("aborted",Jsons.read(new File(dir,"metadata.json")).getString("completion_state"));
        assertEquals("process_end_unknown",Jsons.read(new File(dir,"metadata.json")).getString("stopped_reason"));
        assertTrue(new File(dir,"manifest.json").isFile());
    }
}
