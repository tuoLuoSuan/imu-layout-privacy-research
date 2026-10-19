package org.imulayout.recorder.ui;

import org.imulayout.recorder.core.Jsons;
import org.junit.Test;
import static org.junit.Assert.*;

public class CompletionMessageTest {
    @Test public void connectionFailureShowsActualCause() {
        String message=CompletionMessage.format(true,"joint_bridge_failed","连接停止：Connection refused","");
        assertTrue(message.contains("本机连接中断"));
        assertTrue(message.contains("Connection refused"));
        assertTrue(message.contains("部分记录已保留，可导出"));
        RecorderPresentation p=RecorderPresentation.from(message,false,false);
        assertEquals(RecorderPresentation.Phase.INTERRUPTED,p.phase);
        assertTrue(p.canStart);
        assertFalse(p.canStop);
    }
    @Test public void completedMessageDoesNotAcceptPhysicalClock() {
        String message=CompletionMessage.format(false,"joint_probe_complete","","");
        assertTrue(message.startsWith("已保存"));
        assertFalse(message.contains("同步通过"));
    }
    @Test public void missingCauseDoesNotInventConnectionFailure() {
        String message=CompletionMessage.format(true,"",null,null);
        assertTrue(message.contains("具体停止原因未记录"));
        assertFalse(message.contains("本机连接中断"));
    }
    @Test public void storageAndStopFailureRemainVisible() {
        String message=CompletionMessage.fromMetadata(Jsons.object("completion_state","aborted","stopped_reason","user","stop_failure","drain_timeout","start_error","","storage_error","disk write failed"));
        assertTrue(message.contains("记录收尾超时"));
        assertTrue(message.contains("disk write failed"));
    }
}
