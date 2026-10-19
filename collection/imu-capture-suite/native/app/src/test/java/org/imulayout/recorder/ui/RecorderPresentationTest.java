package org.imulayout.recorder.ui;

import org.junit.Test;
import static org.junit.Assert.*;

public class RecorderPresentationTest {
    @Test public void jointLiveSummaryKeepsStopAvailable() {
        RecorderPresentation p=RecorderPresentation.from("正在联机采集\n手机已连接，请在表上开始\n时长 3 秒\n加速度 301 条 · 角速度 300 条",true,true);
        assertEquals(RecorderPresentation.Phase.RECORDING,p.phase);
        assertTrue(p.canStop);
        assertFalse(p.canStart);
        assertEquals(3,p.seconds);
        assertEquals(301,p.accelerometer);
    }
    @Test public void jointSummaryCannotEnableStopAfterServiceEnds() {
        RecorderPresentation p=RecorderPresentation.from("正在联机采集",false,false);
        assertFalse(p.canStop);
    }
    @Test public void liveSummaryUsesRecordedCountsAndTime() {
        RecorderPresentation p=RecorderPresentation.from("正在采集\n时长 925 秒\n加速度 12345 条 · 角速度 6789 条",true,true);
        assertEquals(RecorderPresentation.Phase.RECORDING,p.phase);
        assertEquals("15:25",p.durationText());
        assertEquals(12345,p.accelerometer);
        assertEquals(6789,p.gyroscope);
        assertFalse(p.canStart);
        assertTrue(p.canStop);
    }
    @Test public void drainingCannotStartOrStopAnotherSession() {
        RecorderPresentation p=RecorderPresentation.from("正在收尾\n时长 61 秒\n加速度 22 条 · 角速度 20 条",true,true);
        assertEquals(RecorderPresentation.Phase.STOPPING,p.phase);
        assertFalse(p.canStart);
        assertFalse(p.canStop);
    }
    @Test public void unknownSummaryNeverFabricatesMeasurements() {
        RecorderPresentation p=RecorderPresentation.from("未识别的新格式",true,true);
        assertEquals("—",p.durationText());
        assertEquals(-1,p.accelerometer);
        assertEquals(-1,p.gyroscope);
        assertFalse(p.canStart);
        assertTrue(p.detail.contains("未识别的新格式"));
    }
    @Test public void interruptedSessionRetainsFailureAndCanStartWhenClosed() {
        String reason="未完整结束：连续运行条件中断\n部分记录已保留，可导出";
        RecorderPresentation p=RecorderPresentation.from(reason,false,false);
        assertEquals(RecorderPresentation.Phase.INTERRUPTED,p.phase);
        assertTrue(p.detail.contains("连续运行条件中断"));
        assertTrue(p.canStart);
        assertFalse(p.canStop);
        assertEquals(-1,p.seconds);
    }
    @Test public void idleIsTheOnlyStateWithInitialZeroCounters() {
        RecorderPresentation p=RecorderPresentation.from("尚未开始",false,false);
        assertEquals("00:00",p.durationText());
        assertEquals(0,p.accelerometer);
        assertEquals(0,p.gyroscope);
        RecorderPresentation saved=RecorderPresentation.from("已保存，可导出；连续性结论请查看完整性报告",false,false);
        assertEquals(RecorderPresentation.Phase.SAVED,saved.phase);
        assertEquals(-1,saved.accelerometer);
    }
}
