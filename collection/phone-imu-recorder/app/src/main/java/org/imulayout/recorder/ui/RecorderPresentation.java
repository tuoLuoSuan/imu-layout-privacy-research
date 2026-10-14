package org.imulayout.recorder.ui;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Read-only presentation of the existing service summary; never controls sensors. */
public final class RecorderPresentation {
    public enum Phase { IDLE, STARTING, RECORDING, STOPPING, SAVED, INTERRUPTED, ERROR, UNKNOWN }
    private static final Pattern TIME=Pattern.compile("时长\\s+(\\d+)\\s+秒");
    private static final Pattern COUNTS=Pattern.compile("加速度\\s+(\\d+)\\s+条\\s*·\\s*角速度\\s+(\\d+)\\s+条");
    public final Phase phase;
    public final String detail;
    public final long seconds,accelerometer,gyroscope;
    public final boolean canStart,canStop;

    private RecorderPresentation(Phase phase,String detail,long seconds,long accelerometer,long gyroscope,boolean busy,boolean running) {
        this.phase=phase;this.detail=detail;this.seconds=seconds;
        this.accelerometer=accelerometer;this.gyroscope=gyroscope;
        canStart=!busy&&!running;
        canStop=running&&phase==Phase.RECORDING;
    }
    public static RecorderPresentation from(String summary,boolean busy,boolean running) {
        String text=summary==null?"":summary.trim();
        String first=text.split("\n",2)[0];
        Phase phase;
        if(first.equals("尚未开始"))phase=Phase.IDLE;
        else if(first.equals("启动中"))phase=Phase.STARTING;
        else if(first.equals("正在采集"))phase=Phase.RECORDING;
        else if(first.equals("正在收尾"))phase=Phase.STOPPING;
        else if(first.startsWith("已保存"))phase=Phase.SAVED;
        else if(first.startsWith("未完整结束")||first.startsWith("采集中断")||first.startsWith("收尾"))phase=Phase.INTERRUPTED;
        else if(first.startsWith("启动失败"))phase=Phase.ERROR;
        else phase=Phase.UNKNOWN;
        long seconds=phase==Phase.IDLE?0:-1,accel=seconds,gyro=seconds;
        Matcher time=TIME.matcher(text),counts=COUNTS.matcher(text);
        if(time.find())seconds=number(time.group(1));
        if(counts.find()){accel=number(counts.group(1));gyro=number(counts.group(2));}
        return new RecorderPresentation(phase,text,seconds,accel,gyro,busy,running);
    }
    private static long number(String text) {
        try{return Long.parseLong(text);}catch(NumberFormatException e){return -1;}
    }
    public String durationText() {
        return seconds<0?"—":String.format(Locale.ROOT,"%02d:%02d",seconds/60,seconds%60);
    }
}
