package org.imulayout.recorder.ui;

import org.imulayout.recorder.core.Jsons;
import org.junit.Test;
import java.io.File;
import java.nio.file.Files;
import static org.junit.Assert.*;

public class SessionEntryTest {
    @Test public void completeShortSessionExplainsUnavailableBaselineWithoutChangingReport() throws Exception {
        File d=complete();
        Jsons.save(new File(d,"integrity_report.json"),Jsons.object("format_version",1,"data_checks_passed",false,"completion","pass","event_continuity","pass","delivery_continuity","pass","storage_integrity","pass","baseline_stability","unknown_or_fail","channels",new org.json.JSONArray().put(Jsons.object("baseline",Jsons.object("valid",false))).put(Jsons.object("baseline",Jsons.object("valid",false)))));
        String before=Jsons.sha256(new File(d,"integrity_report.json"));
        assertEquals("基线未建立",SessionEntry.read(d).qualityText);
        assertEquals(before,Jsons.sha256(new File(d,"integrity_report.json")));
    }
    @Test public void abortedRecordRetainsSavedConnectionCauseWithoutEditingMetadata() throws Exception {
        File d=complete();
        Jsons.save(new File(d,"metadata.json"),Jsons.object("completion_state","aborted","stopped_reason","joint_bridge_failed","stop_failure","","start_error","连接停止：本机时间桥未接受：409 native session/sequence mismatch","joint_bridge_status","连接停止：本机时间桥未接受：409 native session/sequence mismatch"));
        String before=Jsons.sha256(new File(d,"metadata.json"));
        SessionEntry entry=SessionEntry.read(d);
        assertTrue(entry.readWarning.contains("本机连接中断"));
        assertTrue(entry.readWarning.contains("409 native session/sequence mismatch"));
        assertEquals(before,Jsons.sha256(new File(d,"metadata.json")));
    }
    @Test public void readsNewRateAndOldPeriodWithoutRewritingEitherRecord() throws Exception {
        File old=complete(),recent=complete();
        Jsons.save(new File(old,"metadata.json"),Jsons.object("requested_period_us",20000));
        Jsons.save(new File(recent,"metadata.json"),Jsons.object("requested_rate_hz",120,"requested_period_us",8333));
        String original=Jsons.sha256(new File(old,"metadata.json"));
        assertEquals("请求周期 20000 µs",SessionEntry.read(old).frequencyText);
        assertEquals("请求 120 Hz · 8333 µs",SessionEntry.read(recent).frequencyText);
        assertEquals(original,Jsons.sha256(new File(old,"metadata.json")));
        assertEquals("请求频率未知",SessionEntry.read(complete()).frequencyText);
    }
    private File complete() throws Exception {
        File d=Files.createTempDirectory("imu-ui-synthetic-").toFile();
        Jsons.save(new File(d,"metadata.json"),Jsons.object("completion_state","complete","start_wall_ms",1234));
        return d;
    }
    @Test public void normalCompletionNeverHidesFailedQuality() throws Exception {
        File d=complete();
        Jsons.save(new File(d,"integrity_report.json"),Jsons.object("format_version",1,"data_checks_passed",false));
        String before=Jsons.sha256(new File(d,"metadata.json"));
        SessionEntry entry=SessionEntry.read(d);
        assertEquals("正常结束",entry.completionText);
        assertEquals("应用检查未通过",entry.qualityText);
        assertTrue(entry.needsAttention);
        assertEquals(d,entry.directory);
        assertEquals(before,Jsons.sha256(new File(d,"metadata.json")));
    }
    @Test public void internalChecksStillRequireIndependentReview() throws Exception {
        File d=complete();
        Jsons.save(new File(d,"integrity_report.json"),Jsons.object("format_version",1,"data_checks_passed",true));
        assertEquals("待独立核验",SessionEntry.read(d).qualityText);
    }
    @Test public void missingOrUnrecognizedReportsAreUnknown() throws Exception {
        File d=complete();
        assertEquals("检查结果未知",SessionEntry.read(d).qualityText);
        Jsons.save(new File(d,"integrity_report.json"),Jsons.object("format_version",999,"data_checks_passed",true));
        assertEquals("检查结果未知",SessionEntry.read(d).qualityText);
        Jsons.save(new File(d,"integrity_report.json"),Jsons.object("format_version",1,"data_checks_passed","true"));
        assertEquals("检查结果未知",SessionEntry.read(d).qualityText);
    }
    @Test public void malformedMetadataKeepsRecordVisibleWithWarning() throws Exception {
        File d=Files.createTempDirectory("imu-ui-synthetic-broken-").toFile();
        Files.writeString(new File(d,"metadata.json").toPath(),"{broken");
        SessionEntry entry=SessionEntry.read(d);
        assertEquals(d,entry.directory);
        assertEquals("信息无法读取",entry.completionText);
        assertTrue(entry.needsAttention);
        assertFalse(entry.readWarning.isEmpty());
    }
}
