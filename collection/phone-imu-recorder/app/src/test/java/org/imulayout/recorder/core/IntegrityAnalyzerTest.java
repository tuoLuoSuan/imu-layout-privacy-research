package org.imulayout.recorder.core;
import org.junit.Test;
import org.json.*;
import java.io.File;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;
public class IntegrityAnalyzerTest {
    private File make(long gap,boolean duplicate) throws Exception {
        File d=Files.createTempDirectory("imu-synthetic-").toFile();
        for(String c:RecordingContract.CHANNELS){StringBuilder b=new StringBuilder("sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy\n");
            for(int i=0;i<3000;i++){long t=10_000_000_000L+i*20_000_000L+(i>=1500?gap:0);if(duplicate&&i==100)t-=20_000_000;
                b.append(i+1).append(',').append(t).append(',').append(t).append(',').append(t).append(",0,0,9.8,3\n");}
            Files.writeString(new File(d,c+".csv").toPath(),b,StandardCharsets.UTF_8);}
        return d;
    }
    private JSONObject meta(long gap){return Jsons.object("completion_state","complete","collection_start_elapsed_ns",10_000_000_000L,"stop_elapsed_ns",70_000_000_000L+gap,
        "received",new JSONArray().put(3000).put(3000),"enqueued",new JSONArray().put(3000).put(3000),"written",new JSONArray().put(3000).put(3000),
        "confirmed",new JSONArray().put(3000).put(3000),"dropped",new JSONArray().put(0).put(0),"visibility_condition_failed",false,
        "states",new JSONArray().put(Jsons.object("elapsed_ns",10_000_000_000L,"state","foreground")));}
    @Test public void aLargeGapVetoesAnOtherwiseGoodMedian() throws Exception {
        JSONObject r=IntegrityAnalyzer.analyze(make(1_100_000_000L,false),meta(1_100_000_000L));
        assertEquals("fail",r.getString("event_continuity"));
        assertTrue(r.getJSONArray("channels").getJSONObject(0).getJSONObject("event_intervals").getJSONArray("over_1s").length()>0);
    }
    @Test public void hundredMillisecondWarningDoesNotItselfFail() throws Exception {
        JSONObject r=IntegrityAnalyzer.analyze(make(110_000_000L,false),meta(110_000_000L));
        assertEquals("pass",r.getString("event_continuity"));
        assertTrue(r.getJSONArray("warnings").length()>0);
        assertEquals(20_000_000L,r.getJSONArray("channels").getJSONObject(0).getJSONObject("baseline").getLong("median_ns"));
    }
    @Test public void duplicateEventTimestampFails() throws Exception {
        assertEquals("fail",IntegrityAnalyzer.analyze(make(0,true),meta(0)).getString("event_continuity"));
    }
    @Test public void baselineRequiresAtLeastOneThousandPositiveIntervals() throws Exception {
        for(int n:new int[]{1000,1001}){
            File d=Files.createTempDirectory("imu-synthetic-baseline-").toFile();
            for(String c:RecordingContract.CHANNELS){StringBuilder b=new StringBuilder("sequence,sensor_timestamp_ns,received_elapsed_realtime_ns,writer_dequeued_elapsed_realtime_ns,x,y,z,accuracy\n");
                for(int i=0;i<n;i++){long t=12_000_000_000L+i*57_900_000L;b.append(i+1).append(',').append(t).append(',').append(t).append(',').append(t).append(",0,0,9.8,3\n");}
                Files.writeString(new File(d,c+".csv").toPath(),b);}
            JSONObject r=IntegrityAnalyzer.analyze(d,meta(0));
            assertEquals(n==1001,r.getJSONArray("channels").getJSONObject(0).getJSONObject("baseline").getBoolean("valid"));
        }
    }
}
